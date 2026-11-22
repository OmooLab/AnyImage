"""Convert one image Selection into a Cutout Shape."""

import bpy

from ...preferences import (
    DEFAULT_CUTOUT_BOUNDARY_PADDING,
    MAX_CUTOUT_BOUNDARY_PADDING,
    MIN_CUTOUT_BOUNDARY_PADDING,
    configured_cutout_boundary_padding,
)
from ...properties import (
    cutout_alpha_threshold_property,
    cutout_fine_outline_property,
    cutout_edge_length_property,
)
from ...runtime import JobOperator
from ...common.job_image import prepare_recognition_input
from ...common.image_input import cleanup_image_input
from ...common.ai import (
    invoke_ai_setup_if_needed,
    geometry_job_parameters,
)
from ...common.image import image_content_signature, image_rgba, require_image_empty, is_animated_image
from ...common.object import read_conversion_source
from ...common.geometry_image import (
    load_depth_result_image,
    load_normal_result_image,
)
from ...common.viewport import (
    report_image_edit_exception,
)
from ...common.selection import ImageEditWarning, SelectionPath
from .geometry import cutout_selection_mask
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

    _input_path = None
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    selection_path_json: bpy.props.StringProperty(options=_HIDDEN)
    shape: bpy.props.StringProperty(default="SOLID", options=_HIDDEN)
    gesture: bpy.props.StringProperty(default="LASSO", options=_HIDDEN)
    edge_length: cutout_edge_length_property(options=_HIDDEN)
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
            source_rgba = image_rgba(source_object.data)
            self._selection = cutout_selection_mask(
                source_rgba, SelectionPath.from_json(self.selection_path_json), alpha_threshold=self.alpha_threshold,
            )
            setup_result = invoke_ai_setup_if_needed(self)
            if setup_result is not None:
                return setup_result
            self._source_signature = image_content_signature(source_object.data, source_rgba[::-1])
            context.view_layer.objects.active = source_object
            source_object.select_set(True)
            self.boundary_padding = configured_cutout_boundary_padding(context)
            left, top, right, bottom = self._selection.bounds
            self._input_rgba = source_rgba[top:bottom, left:right]
        except (
            ImageEditWarning,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return super().execute(context)

    def request(self, context):
        parameters = geometry_job_parameters(context)
        self._input_path = prepare_recognition_input(self._source_image, self._input_rgba)
        self._input_rgba = None
        return {
            **parameters,
            "input": str(self._input_path),
            "generate_depth": self.shape in DEPTH_CUTOUT_SHAPES,
        }

    def response(self, context, result):
        source_object, pixels = read_conversion_source(self)
        normal_image = None
        depth_image = None
        try:
            normal_image = load_normal_result_image(result.file("object_normal"), source_object)
        except (FileNotFoundError, RuntimeError):
            pass
        try:
            intrinsics = None
            if self.shape in DEPTH_CUTOUT_SHAPES:
                intrinsics = result.value["intrinsics"]
                depth_image = load_depth_result_image(result.file("depth"), source_object)
            create_cutout_shape(
                context, source_object, self.shape, self.edge_length, self._selection,
                depth_image=depth_image, intrinsics=intrinsics,
                normal_image=normal_image, alpha_threshold=self.alpha_threshold,
                fine_outline=self.fine_outline, boundary_padding=self.boundary_padding,
                source_rgba=image_rgba(source_object.data, pixels), gesture=self.gesture, report=self.report,
            )
            if normal_image is None:
                self.report({"WARNING"}, "The normal texture is missing; the shape was created without it")
        except Exception:
            if normal_image is not None and normal_image.users == 0:
                bpy.data.images.remove(normal_image, do_unlink=True)
            if depth_image is not None and depth_image.users == 0:
                bpy.data.images.remove(depth_image, do_unlink=True)
            raise
        return f"{self.shape.replace('_', ' ').title()} is ready"

    def cleanup(self):
        self._input_rgba = None
        cleanup_image_input(self._input_path)
        self._selection = None
        self._source_object = None
        self._source_image = None
        self._source_signature = None
