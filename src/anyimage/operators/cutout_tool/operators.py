import bpy
from ...preferences import configured_cutout_boundary_padding
from ...properties import (
    cutout_alpha_threshold_property,
    cutout_fine_outline_property,
    cutout_edge_length_property,
    cutout_gesture_property,
)
from ...common.image import image_rgba, require_image_empty, is_animated_image
from ...common.color_image import material_color_image
from ...common.selection import ImageEditWarning, SelectionPath, rasterize_selection_path
from ...common.viewport import ImageGesture, deserialize_matrix, report_image_edit_exception
from .construction import _cutout_content_values, build_cutout_shape, push_cutout_undo
from .object import create_shape_object
from .boundary_padding import pad_cutout_images
from .interaction import open_shape_pie
from .preview import CutoutGridPreview, screen_to_grid_matrix

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class CreateCutoutShape(bpy.types.Operator):
    bl_idname = "anyimage.create_cutout_shape"
    bl_label = "Cutout Selection to Shape"
    bl_options = {"INTERNAL"}

    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    selection_path_json: bpy.props.StringProperty(options=_HIDDEN)
    shape: bpy.props.StringProperty(default="SOLID", options=_HIDDEN)
    gesture: bpy.props.StringProperty(default="LASSO", options=_HIDDEN)
    edge_length: cutout_edge_length_property(options=_HIDDEN)
    alpha_threshold: cutout_alpha_threshold_property()
    fine_outline: cutout_fine_outline_property()

    def execute(self, context):
        try:
            source = require_image_empty(self.source_object_name)
            if is_animated_image(source.data):
                raise ValueError("Cutout currently supports still images")
            if self.shape not in {"FLAT", "SOLID"}:
                raise ValueError(f"Unsupported Cutout shape: {self.shape}")
            selection = rasterize_selection_path(
                tuple(source.data.size),
                SelectionPath.from_json(self.selection_path_json),
                antialias=True,
            )
            rgba = image_rgba(source.data)
            context.view_layer.objects.active = source
            source.select_set(True)
            left, top, right, bottom = selection.bounds
            values = _cutout_content_values(
                rgba[top:bottom, left:right, 3],
                selection.values,
                alpha_threshold=self.alpha_threshold,
            )
            shape = build_cutout_shape(
                context,
                source,
                self.edge_length,
                values,
                selection.bounds,
                self.alpha_threshold,
                self.fine_outline,
                self.report,
            )
            with material_color_image(source.data, bounds=selection.bounds, rgba=rgba) as color:
                pad_cutout_images(
                    color, None, None, shape.mask, 0.5, configured_cutout_boundary_padding(context)
                )
                create_shape_object(
                    context,
                    source,
                    self.shape,
                    selection.bounds,
                    shape,
                    color_image=color,
                    gesture=self.gesture,
                )
            push_cutout_undo(self.shape)
        except (ImageEditWarning, OSError, RuntimeError, TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return {"FINISHED"}


class SelectCutoutSelection(ImageGesture, bpy.types.Operator):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"
    bl_description = (
        "Select an Image Empty area with a lasso or polyline, then choose its mesh shape"
    )
    bl_options = {"INTERNAL"}
    active_tool_id = "anyimage.cutout_lasso"
    resolve_on_press = True
    gesture: cutout_gesture_property()

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    source_matrix_data: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    show_shape_menu = staticmethod(open_shape_pie)

    _pie_event = None
    _polyline_confirm_type = None
    _grid_preview = None

    def _draw_selection_fill(self, color):
        context = bpy.context
        try:
            transform = screen_to_grid_matrix(
                (context.region.width, context.region.height),
                context.region_data.perspective_matrix,
                deserialize_matrix(self.source_matrix_data),
                context.scene.anyimage_settings.cutout_edge_length,
            )
        except ValueError:
            # An edge-on image plane has no invertible screen projection.
            return super()._draw_selection_fill(color)
        if self._grid_preview is None:
            self._grid_preview = CutoutGridPreview()
        self._grid_preview.draw(self._fill_triangles, color, transform)

    def _finish(self, context):
        self._grid_preview = None
        super()._finish(context)

    def _read_gesture_settings(self, context):
        self.gesture = context.scene.anyimage_settings.cutout_gesture

    def _set_status(self, context):
        action = (
            "click points; click start, double-click, or Enter for shapes; Backspace removes"
            if self.gesture == "POLYLINE"
            else "drag and release for shapes"
        )
        context.workspace.status_text_set(
            bpy.app.translations.pgettext_iface(
                "Cutout {gesture}: {action}; RMB or Esc cancels"
            ).format(
                gesture=bpy.app.translations.pgettext_iface(self.gesture.title()),
                action=bpy.app.translations.pgettext_iface(action),
            )
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
        self.show_shape_menu(
            context,
            self._pie_event,
            source_object,
            selection_path,
            gesture=self.gesture,
        )
        return {"FINISHED"}
