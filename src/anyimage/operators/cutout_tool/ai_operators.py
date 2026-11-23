"""Convert one image Selection into a Cutout Shape."""

import bpy

from ...ai_preferences import configured_max_ai_input_size
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
from ...common.image_input import cleanup_image_input, prepare_ai_input
from ...common.ai import (
    ai_ready,
    invoke_ai_setup_if_needed,
    geometry_job_parameters,
)
from ...common.image import image_rgba, require_image_empty, is_animated_image
from ...common.geometry_image import (
    load_depth_result_image,
    load_normal_result_image,
)
from ...common.viewport import (
    report_image_edit_exception,
)
from ...common.selection import ImageEditWarning, SelectionPath
from .geometry import cutout_selection_mask
from .object import CutoutSource, create_cutout_shape
from .operators import CreateCutoutShape, SelectCutoutSelection as SharedSelection, flat_and_solid_buttons, open_shape_pie
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
            self.boundary_padding = configured_cutout_boundary_padding(context)
            self._input_rgba = source_rgba
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
        self._cutout = CutoutSource.capture(context, self._source_object, self._selection.bounds, self._input_rgba)
        left, top, right, bottom = self._selection.bounds
        self._input_path = prepare_ai_input(
            self._source_object.data, self._input_rgba, bounds=self._selection.bounds,
            max_input_size=configured_max_ai_input_size(context),
        )
        self._input_rgba = self._source_object = None
        return {
            **parameters,
            "input": str(self._input_path),
            "output_size": (right - left, bottom - top),
            "generate_depth": self.shape in DEPTH_CUTOUT_SHAPES,
        }

    def response(self, context, result):
        source = self._cutout
        if source.collection != context.scene.collection and source.collection not in context.scene.collection.children_recursive:
            raise RuntimeError("The cutout collection is no longer available")
        normal_image = None
        depth_image = None
        try:
            normal_image = load_normal_result_image(result.file("object_normal"), f"{source.image_name}_normal.png")
        except (FileNotFoundError, RuntimeError):
            pass
        try:
            intrinsics = None
            if self.shape in DEPTH_CUTOUT_SHAPES:
                intrinsics = result.value["intrinsics"]
                depth_image = load_depth_result_image(result.file("depth"), f"{source.image_name}_depth.exr")
            create_cutout_shape(
                context, source, self.shape, self.edge_length, self._selection,
                depth_image=depth_image, intrinsics=intrinsics,
                normal_image=normal_image, alpha_threshold=self.alpha_threshold,
                fine_outline=self.fine_outline, boundary_padding=self.boundary_padding,
                gesture=self.gesture, report=self.report,
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
        self._cutout = None


class SelectCutoutSelection(SharedSelection):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"

    @staticmethod
    def show_shape_menu(context, event, source_object, selection_path, *, gesture="LASSO"):
        buttons = None
        if ai_ready():
            basic = CutoutSelectionToShape if context.scene.anyimage_settings.cutout_generate_normal else CreateCutoutShape
            buttons = (
                *flat_and_solid_buttons(basic),
                ("DEPTH_SYMMETRY", "META_BALL", CutoutSelectionToShape),
                ("DEPTH_SOLID", "SURFACE_NCURVE", CutoutSelectionToShape),
            )
        open_shape_pie(
            context,
            event,
            source_object,
            selection_path,
            gesture=gesture,
            buttons=buttons,
        )
