"""Convert one image Selection into a Cutout Shape."""

import json

import bpy

from ...preferences import (
    DEFAULT_CUTOUT_BOUNDARY_PADDING,
    MAX_CUTOUT_BOUNDARY_PADDING,
    MIN_CUTOUT_BOUNDARY_PADDING,
    addon_preferences,
    configured_cutout_boundary_padding,
    configured_geometry_model,
    configured_max_ai_input_size,
)
from ...properties import (
    cutout_alpha_threshold_property,
    cutout_fine_outline_property,
    cutout_gesture_property,
    cutout_edge_length_property,
)
from ...runtime import JobOperatorBase
from ...server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ...server.media.resolution import (
    DEFAULT_MAX_AI_INPUT_SIZE,
    MAX_MAX_AI_INPUT_SIZE,
    MIN_MAX_AI_INPUT_SIZE,
)
from ...common.ai import (
    invoke_ai_setup_if_needed,
    moge2_parameters,
    production_device,
    require_environment,
    require_input_path,
    require_model,
)
from ...common.image import (
    image_rgba,
    load_normal_result_image,
    require_image_empty,
    is_animated_image,
)
from ...common.depth import load_depth_metadata, load_depth_result_image
from ...common.color_image import (
    cleanup_material_color_input,
    load_material_color_image,
    material_analysis_input,
    material_color_image,
    prepare_material_color_input,
)
from ...common.viewport import (
    ImageGesture,
    report_image_edit_exception,
)
from ...common.selection import (
    ImageEditWarning,
    SelectionPath,
    rasterize_selection_path,
)
from .geometry import (
    CUTOUT_ALPHA_THRESHOLD,
    build_base_shape,
    effective_cutout_edge_length,
)
from .interaction import CUTOUT_SHAPE_OPERATOR_ID, open_shape_pie
from .object import (
    NormalMode,
    create_shape_object,
)
from .shape import CUTOUT_SHAPES, DEPTH_CUTOUT_SHAPES
from .boundary_padding import pad_cutout_images

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


def normal_mode_for_shape(shape, generate_normal):
    if shape in DEPTH_CUTOUT_SHAPES:
        return NormalMode.OBJECT
    if not generate_normal:
        return NormalMode.NONE
    return NormalMode.TANGENT


def shape_uses_depth(shape):
    return shape in {"DEPTH_SOLID", "DEPTH_SYMMETRY"}


def create_cutout_shape(
    context,
    source_object,
    shape,
    edge_length,
    content_values,
    content_bounds,
    *,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    fine_outline=False,
    depth_image=None,
    depth_metadata=None,
    normal_image=None,
    normal_mode=NormalMode.NONE,
    boundary_padding=DEFAULT_CUTOUT_BOUNDARY_PADDING,
    color_image,
    gesture="LASSO",
    report=None,
):
    effective_length = effective_cutout_edge_length(
        context, source_object, edge_length, content_values, content_bounds, alpha_threshold
    )
    if report is not None and effective_length > edge_length * (1 + 1e-6):
        units = context.scene.unit_settings
        label = bpy.utils.units.to_string(
            units.system if units.system != "NONE" else "METRIC", "LENGTH",
            effective_length * units.scale_length, precision=4,
        )
        report({"INFO"}, f"Effective Edge Length: {label}")
    base_shape = build_base_shape(
        context,
        source_object,
        effective_length,
        content_values,
        content_bounds,
        alpha_threshold=alpha_threshold,
        fine_outline=fine_outline,
    )
    pad_cutout_images(
        color_image,
        depth_image,
        depth_metadata,
        base_shape.mask,
        0.5,
        boundary_padding,
    )
    result = create_shape_object(
        context,
        source_object,
        shape,
        content_values,
        content_bounds,
        base_shape,
        depth_image=depth_image,
        depth_metadata=depth_metadata,
        normal_image=normal_image,
        normal_mode=normal_mode,
        color_image=color_image,
        gesture=gesture,
    )
    undo_message = f"Convert to {shape.replace('_', ' ').title()}"
    if "FINISHED" not in bpy.ops.ed.undo_push(message=undo_message):
        raise RuntimeError(f"Unable to create the {undo_message} Undo step")
    return result


def _cutout_content_values(
    source_alpha, selection_values=None, *, alpha_threshold=CUTOUT_ALPHA_THRESHOLD
):
    """Combine local image Alpha with optional pure Selection geometry."""
    import numpy as np

    alpha = np.asarray(source_alpha, dtype=np.float32)
    if alpha.ndim != 2:
        raise ValueError("The Cutout source Alpha must be two-dimensional")
    if selection_values is None:
        values = alpha.copy()
    else:
        selection = np.asarray(selection_values, dtype=np.float32)
        if alpha.shape != selection.shape:
            raise ValueError("The Cutout source Alpha does not match the Selection")
        values = alpha * selection
    if not np.any((values > 0.0) & (values >= alpha_threshold)):
        raise ImageEditWarning(
            "The Cutout selection contains no visible image pixels"
        )
    return values


def _generated_color_result(input_path, source_bounds):
    image = load_material_color_image(input_path)
    try:
        alpha = image_rgba(image)[:, :, 3]
    except Exception:
        if image.users == 0:
            bpy.data.images.remove(image, do_unlink=True)
        raise
    return image, alpha, source_bounds


def cutout_geometry_settings(context):
    preferences = addon_preferences(context)
    model = configured_geometry_model(context)
    return (
        model,
        int(getattr(preferences, "geometry_resolution_level", 5)),
    )


class CutoutSelectionToShape(JobOperatorBase, bpy.types.Operator):
    bl_idname = CUTOUT_SHAPE_OPERATOR_ID
    bl_label = "Cutout Selection to Shape"
    bl_description = "Build the image selection as a Cutout shape"
    bl_options = {"INTERNAL"}
    job_type = "generate-cutout-artifacts"
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
    def _needs_generation(self):
        return self.shape in DEPTH_CUTOUT_SHAPES or self.generate_normal

    def execute(self, context):
        try:
            source_object = require_image_empty(self.source_object_name)
            if is_animated_image(source_object.data):
                raise ValueError("Cutout currently supports still images")
            if self.shape not in CUTOUT_SHAPES:
                raise ValueError(f"Unsupported Cutout shape: {self.shape}")
            selection_path = SelectionPath.from_json(self.selection_path_json)
            selection_mask = rasterize_selection_path(
                tuple(source_object.data.size),
                selection_path,
                antialias=True,
            )
            source_rgba = image_rgba(source_object.data)
            context.view_layer.objects.active = source_object
            source_object.select_set(True)
            self.max_ai_input_size = configured_max_ai_input_size(context)
            self.boundary_padding = configured_cutout_boundary_padding(context)
            if not self._needs_generation():
                left, top, right, bottom = selection_mask.bounds
                content_values = _cutout_content_values(
                    source_rgba[top:bottom, left:right, 3],
                    selection_mask.values,
                    alpha_threshold=self.alpha_threshold,
                )
                with material_color_image(source_object.data, bounds=selection_mask.bounds, rgba=source_rgba) as color_image:
                    create_cutout_shape(
                        context, source_object, self.shape, self.edge_length,
                        content_values, selection_mask.bounds,
                        alpha_threshold=self.alpha_threshold,
                        fine_outline=self.fine_outline, color_image=color_image,
                        boundary_padding=self.boundary_padding,
                        gesture=self.gesture,
                        report=self.report,
                    )
                return {"FINISHED"}
            setup_result = invoke_ai_setup_if_needed(self)
            if setup_result is not None:
                return setup_result
            self.model, self.resolution_level = cutout_geometry_settings(context)
            self.selection_bounds_json = json.dumps(
                selection_mask.bounds,
                separators=(",", ":"),
            )
            self._selection_mask = selection_mask
            self.color_path = str(prepare_material_color_input(
                source_object.data, selection_mask.bounds, source_rgba,
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
        result = super().execute(context)
        if "CANCELLED" in result:
            cleanup_material_color_input(self.color_path)
        return result

    def request(self, context):
        require_environment()
        source_path = require_input_path(self.input_path)
        generate_depth = shape_uses_depth(self.shape)
        normal_mode = normal_mode_for_shape(self.shape, self.generate_normal)
        if generate_depth or normal_mode != NormalMode.NONE:
            require_model(self.model)
        parameters = {
            "input": str(source_path),
            "device": production_device().lower(),
            "generate_depth": generate_depth,
            "normal_mode": normal_mode.value,
            "max_input_size": int(self.max_ai_input_size),
        }
        if generate_depth or normal_mode != NormalMode.NONE:
            parameters.update(
                model=self.model,
                resolution_level=self.resolution_level,
            )
            parameters.update(
                moge2_parameters(
                    source_path,
                    self.model,
                    self.resolution_level,
                )
            )
        return parameters

    def response(self, context, result):
        source_object = require_image_empty(self.source_object_name)
        source_bounds = tuple(json.loads(self.selection_bounds_json))
        color_image, source_alpha, color_bounds = _generated_color_result(
            self.color_path,
            source_bounds,
        )
        value = result.value if isinstance(result.value, dict) else {}
        normal_image = None
        depth_image = None
        try:
            selection_mask = getattr(self, "_selection_mask", None)
            if selection_mask is None:
                raise RuntimeError("The Cutout Selection is no longer available")
            content_values = _cutout_content_values(
                source_alpha,
                selection_mask.values,
                alpha_threshold=self.alpha_threshold,
            )
            content_bounds = color_bounds
            normal_mode = normal_mode_for_shape(self.shape, self.generate_normal)
            normal_key = f"{normal_mode.value.lower()}_normal"
            if normal_key in value:
                normal_image = load_normal_result_image(
                    result.file(normal_key),
                    source_object,
                )
            depth_metadata = None
            if shape_uses_depth(self.shape):
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
                content_bounds,
                depth_image=depth_image,
                depth_metadata=depth_metadata,
                normal_image=normal_image,
                normal_mode=normal_mode,
                alpha_threshold=self.alpha_threshold,
                fine_outline=self.fine_outline,
                boundary_padding=self.boundary_padding,
                color_image=color_image,
                gesture=self.gesture,
                report=self.report,
            )
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


class SelectCutoutSelection(ImageGesture, bpy.types.Operator):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"
    bl_description = "Select an Image Empty area with a lasso or polyline, then choose its mesh shape"
    bl_options = {"INTERNAL"}
    active_tool_id = "anyimage.cutout_lasso"
    resolve_on_press = True
    gesture: cutout_gesture_property()

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    source_matrix_data: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    _pie_event = None
    _polyline_confirm_type = None

    def _read_gesture_settings(self, context):
        self.gesture = context.scene.anyimage_settings.cutout_gesture

    def _set_status(self, context):
        action = (
            "click points; click start, double-click, or Enter for shapes; Backspace removes"
            if self.gesture == "POLYLINE" else "drag and release for shapes"
        )
        context.workspace.status_text_set(
            f"Cutout {self.gesture.title()}: {action}; RMB or Esc cancels"
        )

    def invoke(self, context, event):
        self._polyline_confirm_type = None
        self._pie_event = event
        return super().invoke(context, event)

    def modal(self, context, event):
        self._pie_event = event
        return ImageGesture.modal(self, context, event)

    def _confirm_polyline(self, context):
        if len(self._path) >= 3:
            self._polyline_confirm_type = self._pie_event.type
        return {"RUNNING_MODAL"}

    def _modal_polyline(self, context, event):
        if self._polyline_confirm_type is not None:
            if event.type == self._polyline_confirm_type and event.value == "RELEASE":
                self._polyline_confirm_type = None
                return ImageGesture._confirm_polyline(self, context)
            return {"RUNNING_MODAL"}
        return ImageGesture._modal_polyline(self, context, event)

    def _submit_selection_path(self, context, selection_path):
        try:
            source_object = require_image_empty(self.source_object_name)
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        open_shape_pie(
            context,
            self._pie_event,
            source_object,
            selection_path,
            gesture=self.gesture,
        )
        return {"FINISHED"}
