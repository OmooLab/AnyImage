import bpy
from ...preferences import configured_cutout_boundary_padding
from ...properties import (
    cutout_alpha_threshold_property,
    cutout_fine_outline_property,
    cutout_edge_length_property,
    cutout_gesture_property,
)
from ...common.image import image_rgba, require_image_empty, is_animated_image
from ...common.selection import ImageEditWarning, SelectionPath
from ...common.image_gesture import ImageGesture
from ...common.viewport import report_image_edit_exception
from .geometry import cutout_selection_mask
from .object import CutoutSource, create_cutout_shape
from .shape import CUTOUT_SHAPE_LABELS
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
            rgba = image_rgba(source.data)
            selection = cutout_selection_mask(
                rgba, SelectionPath.from_json(self.selection_path_json), alpha_threshold=self.alpha_threshold,
            )
            context.view_layer.objects.active = source
            source.select_set(True)
            create_cutout_shape(
                context, CutoutSource.capture(context, source, selection.bounds, rgba),
                self.shape, self.edge_length, selection,
                alpha_threshold=self.alpha_threshold,
                fine_outline=self.fine_outline,
                boundary_padding=configured_cutout_boundary_padding(context),
                gesture=self.gesture, report=self.report,
            )
        except (ImageEditWarning, OSError, RuntimeError, TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return {"FINISHED"}


def flat_and_solid_buttons(operator):
    return (("FLAT", "MESH_GRID", operator), ("SOLID", "MESH_UVSPHERE", operator))


def open_shape_pie(
    context,
    event,
    source_object,
    selection_path,
    *,
    gesture="LASSO",
    buttons=None,
):
    if buttons is None:
        buttons = flat_and_solid_buttons(CreateCutoutShape)
    settings = context.scene.anyimage_settings
    parameters = {
        "source_object_name": source_object.name,
        "selection_path_json": selection_path.to_json(),
        "edge_length": settings.cutout_edge_length,
        "alpha_threshold": settings.cutout_alpha_threshold,
        "fine_outline": settings.cutout_fine_outline,
        "gesture": gesture,
    }

    def draw(menu, _context):
        pie = menu.layout.menu_pie()
        for shape, icon, operator_type in buttons:
            operator = pie.operator(
                operator_type.bl_idname, text=CUTOUT_SHAPE_LABELS[shape], text_ctxt="AnyImage", icon=icon,
            )
            operator.shape = shape
            for name, value in parameters.items():
                setattr(operator, name, value)

    context.window_manager.popup_menu_pie(
        event,
        draw,
        title="Cutout Shape",
        icon="MESH_DATA",
    )


class SelectCutoutSelection(ImageGesture, bpy.types.Operator):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"
    bl_description = (
        "Select an Image Empty area with a lasso or polyline, then choose its mesh shape"
    )
    bl_options = {"INTERNAL"}
    finish_label = "Choose Shape"
    active_tool_id = "anyimage.cutout_lasso"
    gesture: cutout_gesture_property()


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
                self._source_matrix,
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

    def _submit_selection_path(self, context, source_object, selection_path):
        self.show_shape_menu(
            context,
            self._pie_event,
            source_object,
            selection_path,
            gesture=self.gesture,
        )
        return {"FINISHED"}
