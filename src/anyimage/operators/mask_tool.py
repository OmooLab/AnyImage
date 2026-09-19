import bpy

from ..common.image import (
    create_image_edit_result,
    image_empty_bounds,
    image_rgba,
    replace_empty_image,
    require_image_empty,
)
from ..common.selection import (
    rasterize_selection_path,
    rasterize_selection_union,
    SelectionPath,
)
from ..common.viewport import (
    brush_footprint_polygons,
    ImageGesture,
    image_edit_point_keymap,
    report_image_edit_exception,
    screen_path_to_image_pixels,
)
from ..properties import (
    mask_gesture_property,
    mask_mode_property,
    mask_radius_property,
)

MASK_TOOL_ID = "anyimage.mask"


def compose_alpha(source_alpha, mask_values, mode):
    """Compose source Alpha with one same-shaped Mask."""
    import numpy as np

    alpha = np.asarray(source_alpha, dtype=np.float32)
    mask = np.asarray(mask_values, dtype=np.float32)
    if alpha.shape != mask.shape:
        raise ValueError("The source Alpha and Mask must have the same shape")
    mode = str(mode)
    if mode == "SET":
        result = alpha * mask
    elif mode == "EXTEND":
        result = np.maximum(alpha, mask)
    elif mode == "SUBTRACT":
        result = alpha * (1.0 - mask)
    else:
        raise ValueError(f"Unsupported Mask mode: {mode}")
    return np.clip(result, 0.0, 1.0)


def apply_alpha_mask(source_rgba, selection_mask, mode):
    """Apply one Selection Mask to current Alpha without changing the canvas."""
    import numpy as np

    rgba = np.asarray(source_rgba, dtype=np.float32).copy()
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("The source image must contain RGBA pixels")
    values = selection_mask.full_values((rgba.shape[1], rgba.shape[0]))
    rgba[:, :, 3] = compose_alpha(rgba[:, :, 3], values, mode)
    return np.flipud(rgba).ravel()


def rasterize_brush_path(image_size, path, radius, project_path):
    """Project the shared Brush footprint and antialias its complete union."""
    paths = tuple(
        SelectionPath(points=tuple(project_path(polygon)))
        for polygon in brush_footprint_polygons(path, radius)
    )
    return rasterize_selection_union(image_size, paths, antialias=True)


class EditImageAlpha(ImageGesture, bpy.types.Operator):
    bl_idname = "anyimage.edit_image_alpha"
    bl_label = "Edit Image Alpha"
    bl_description = "Hide or reveal image areas with a lasso, brush, or polyline."
    bl_options = {"UNDO"}
    active_tool_id = MASK_TOOL_ID
    resolve_on_press = True

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    source_matrix_data: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    gesture: mask_gesture_property()
    mode: mask_mode_property()
    radius: mask_radius_property()

    def _read_gesture_settings(self, context):
        settings = context.scene.anyimage_settings
        self.gesture = str(settings.mask_gesture)
        self.mode = str(settings.mask_mode)
        self.radius = int(settings.mask_radius)

    def _set_status(self, context):
        if self.gesture == "BRUSH":
            action = f"paint with radius {self.radius} px"
        elif self.gesture == "POLYLINE":
            action = (
                "click points; click start, double-click, or Enter to finish; "
                "Backspace removes"
            )
        else:
            action = "draw and release"
        context.workspace.status_text_set(
            f"Mask {self.gesture.title()}: {action}; {self.mode.title()}; "
            "RMB or Esc cancels"
        )

    def _submit_selection_path(self, context, selection_path):
        source_object = require_image_empty(self.source_object_name)
        selection_mask = rasterize_selection_path(
            tuple(source_object.data.size),
            selection_path,
            antialias=True,
        )
        return self._apply_mask(context, source_object, selection_mask)

    def _complete_brush(self, context, source_object, matrix):
        image_size = tuple(source_object.data.size)
        local_bounds = image_empty_bounds(source_object)
        selection_mask = rasterize_brush_path(
            image_size,
            self._path,
            self.radius,
            lambda path: screen_path_to_image_pixels(
                path,
                context.region,
                context.region_data,
                matrix,
                local_bounds,
                image_size,
                simplify=False,
            ),
        )
        return self._apply_mask(context, source_object, selection_mask)

    def _apply_mask(self, context, source_object, selection_mask):
        try:
            source_image = source_object.data
            pixels = apply_alpha_mask(
                image_rgba(source_image),
                selection_mask,
                self.mode,
            )
            result_image = create_image_edit_result(
                source_image,
                pixels,
                tuple(source_image.size),
            )
            replace_empty_image(source_object, result_image)
        except (RuntimeError, TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return {"FINISHED"}


class MaskTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = MASK_TOOL_ID
    bl_label = "Mask"
    bl_description = "Hide or reveal image areas with a lasso, brush, or polyline."
    bl_icon = "ops.sculpt.lasso_mask"
    bl_operator = EditImageAlpha.bl_idname
    bl_cursor = "PAINT_CROSS"
    bl_keymap = image_edit_point_keymap(EditImageAlpha.bl_idname)

    def draw_settings(context, layout, _tool):
        settings = context.scene.anyimage_settings
        layout.prop(settings, "mask_gesture")
        layout.prop(settings, "mask_mode", expand=True, icon_only=True)
        if settings.mask_gesture == "BRUSH":
            layout.prop(settings, "mask_radius")
