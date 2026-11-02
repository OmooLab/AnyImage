"""Convert one image Selection into a Cutout Shape."""

import json

import bpy

from ...preferences import (
    DEFAULT_CUTOUT_BOUNDARY_PADDING,
    MAX_CUTOUT_BOUNDARY_PADDING,
    MIN_CUTOUT_BOUNDARY_PADDING,
    addon_preferences,
    configured_cutout_boundary_padding,
)
from ...ai_preferences import configured_geometry_model, configured_max_ai_input_size
from ...properties import (
    cutout_alpha_threshold_property,
    cutout_fine_outline_property,
    cutout_edge_length_property,
)
from ...runtime import JobOperator
from ...server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ...server.media.resolution import (
    DEFAULT_MAX_AI_INPUT_SIZE,
    MAX_MAX_AI_INPUT_SIZE,
    MIN_MAX_AI_INPUT_SIZE,
)
from ...common.job_image import material_analysis_input
from ...common.ai import (
    invoke_ai_setup_if_needed,
    geometry_job_parameters,
    production_device,
    require_environment,
    require_input_path,
    require_model,
)
from ...common.image import image_content_signature, image_rgba, require_image_empty, is_animated_image
from ...common.image_target import require_conversion_source
from ...common.geometry_image import (
    load_depth_metadata,
    load_depth_result_image,
    load_normal_result_image,
)
from ...common.color_image import (
    cleanup_material_color_input,
    load_material_color_image,
    prepare_material_color_input,
)
from ...common.viewport import (
    report_image_edit_exception,
)
from ...common.selection import (
    ImageEditWarning,
    SelectionPath,
    rasterize_selection_path,
)
from .geometry import cutout_content_values
from .object import create_cutout_shape
from .shape import CUTOUT_NODE_GROUP_NAMES, DEPTH_CUTOUT_SHAPES

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class CutoutSelectionToShape(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.cutout_selection_to_shape"
    bl_label = "Cutout Selection to Shape"
    bl_description = "Build the image selection as a Cutout shape"
    bl_options = {"INTERNAL"}
    job_type = "generate_cutout_artifacts"
    starting_message = "Generating Cutout artifacts"

    input_path: bpy.props.StringProperty(options=_HIDDEN)
    color_path: bpy.props.StringProperty(options=_HIDDEN)
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    selection_path_json: bpy.props.StringProperty(options=_HIDDEN)
    selection_bounds_json: bpy.props.StringProperty(options=_HIDDEN)
    shape: bpy.props.StringProperty(default="SOLID", options=_HIDDEN)
    gesture: bpy.props.StringProperty(default="LASSO", options=_HIDDEN)
    edge_length: cutout_edge_length_property(options=_HIDDEN)
    model: bpy.props.StringProperty(
        default=DEFAULT_GEOMETRY_MODEL_KEY,
        options=_HIDDEN,
    )
    resolution_level: bpy.props.IntProperty(
        default=5,
        min=0,
        max=9,
        options=_HIDDEN,
    )
    max_ai_input_size: bpy.props.IntProperty(
        default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE,
        max=MAX_MAX_AI_INPUT_SIZE,
        options=_HIDDEN,
    )
    generate_normal: bpy.props.BoolProperty(default=False, options=_HIDDEN)
    alpha_threshold: cutout_alpha_threshold_property()
    fine_outline: cutout_fine_outline_property()
    boundary_padding: bpy.props.FloatProperty(
        default=DEFAULT_CUTOUT_BOUNDARY_PADDING,
        min=MIN_CUTOUT_BOUNDARY_PADDING,
        max=MAX_CUTOUT_BOUNDARY_PADDING,
        options=_HIDDEN,
    )

    def execute(self, context):
        try:
            source_object = require_image_empty(self.source_object_name)
            self._source_object = source_object
            self._source_image = source_object.data
            if is_animated_image(source_object.data):
                raise ValueError("Cutout currently supports still images")
            if self.shape not in CUTOUT_NODE_GROUP_NAMES:
                raise ValueError(f"Unsupported Cutout shape: {self.shape}")
            selection_path = SelectionPath.from_json(self.selection_path_json)
            selection_mask = rasterize_selection_path(
                tuple(source_object.data.size),
                selection_path,
                antialias=True,
            )
            source_rgba = image_rgba(source_object.data)
            self._source_signature = image_content_signature(source_object.data, source_rgba[::-1])
            context.view_layer.objects.active = source_object
            source_object.select_set(True)
            self.max_ai_input_size = configured_max_ai_input_size(context)
            self.boundary_padding = configured_cutout_boundary_padding(context)
            setup_result = invoke_ai_setup_if_needed(self)
            if setup_result is not None:
                return setup_result
            self.model = configured_geometry_model(context)
            self.resolution_level = int(getattr(addon_preferences(context), "geometry_resolution_level", 5))
            self.selection_bounds_json = json.dumps(
                selection_mask.bounds,
                separators=(",", ":"),
            )
            self._selection_mask = selection_mask
            self.color_path = str(prepare_material_color_input(
                source_object.data,
                selection_mask.bounds,
                source_rgba,
            ))
            self.input_path = str(material_analysis_input(self.color_path))
        except (
            ImageEditWarning,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            cleanup_material_color_input(getattr(self, "color_path", None))
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return super().execute(context)

    def request(self, context):
        require_environment()
        source_path = require_input_path(self.input_path)
        generate_depth = self.shape in DEPTH_CUTOUT_SHAPES
        generate_normal = generate_depth or self.generate_normal
        if generate_normal:
            require_model(self.model)
        parameters = {
            "input": str(source_path),
            "device": production_device().lower(),
            "generate_depth": generate_depth,
            "generate_normal": generate_normal,
            "max_input_size": int(self.max_ai_input_size),
        }
        if generate_normal:
            parameters.update(
                geometry_job_parameters(
                    source_path,
                    self.model,
                    self.resolution_level,
                )
            )
        return parameters

    def response(self, context, result):
        source_object = require_conversion_source(self)
        source_bounds = tuple(json.loads(self.selection_bounds_json))
        color_image = load_material_color_image(self.color_path)
        value = result.value if isinstance(result.value, dict) else {}
        normal_image = None
        depth_image = None
        normal_missing = False
        try:
            selection_mask = getattr(self, "_selection_mask", None)
            if selection_mask is None:
                raise RuntimeError("The Cutout Selection is no longer available")
            content_values = cutout_content_values(
                image_rgba(color_image)[..., 3],
                selection_mask.values,
                alpha_threshold=self.alpha_threshold,
            )
            if self.shape in DEPTH_CUTOUT_SHAPES or self.generate_normal:
                try:
                    if "object_normal" not in value:
                        raise FileNotFoundError("object_normal")
                    normal_path = result.file("object_normal")
                    normal_image = load_normal_result_image(normal_path, source_object)
                except (FileNotFoundError, RuntimeError):
                    normal_missing = True
            depth_metadata = None
            if self.shape in DEPTH_CUTOUT_SHAPES:
                depth_metadata = load_depth_metadata(result.file("depth_metadata"))
                depth_image = load_depth_result_image(
                    result.file("depth"),
                    source_object,
                    depth_metadata,
                )
            create_cutout_shape(
                context,
                source_object,
                self.shape,
                self.edge_length,
                content_values,
                source_bounds,
                depth_image=depth_image,
                depth_metadata=depth_metadata,
                normal_image=normal_image,
                alpha_threshold=self.alpha_threshold,
                fine_outline=self.fine_outline,
                boundary_padding=self.boundary_padding,
                color_image=color_image,
                gesture=self.gesture,
                report=self.report,
            )
            if normal_missing:
                self.report({"WARNING"}, "The normal texture is missing; the shape was created without it")
        except Exception:
            if normal_image is not None and normal_image.users == 0:
                bpy.data.images.remove(normal_image, do_unlink=True)
            if depth_image is not None and depth_image.users == 0:
                bpy.data.images.remove(depth_image, do_unlink=True)
            if color_image.users == 0:
                bpy.data.images.remove(color_image, do_unlink=True)
            raise
        return f"{self.shape.replace('_', ' ').title()} is ready"

    def cleanup(self):
        cleanup_material_color_input(self.color_path)
        self._source_object = None
        self._source_image = None
        self._source_signature = None
