import bpy

from .operators.cutout_tool import SelectCutoutSelection
from .operators.frame_tool import FrameImages
from .operators.frame_tool.operators import FRAME_TOOL_ID
from .operators.mask_tool import EditImageAlpha, MASK_TOOL_ID
from .operators.rectify_tool import RectifyImagePerspective
from .operators.rectify_tool.operators import RECTIFY_TOOL_ID


def image_edit_keymap(operator_id, *events):
    return (
        *((operator_id, {"type": "LEFTMOUSE", "value": value}, None) for value in events),
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK"},
         {"properties": [("deselect_all", True)]}),
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK", "shift": True},
         {"properties": [("toggle", True)]}),
    )


class FrameTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = FRAME_TOOL_ID
    # Blender uses its Operator translation context for tool labels. The
    # zero-width suffix gives our short labels their own translation keys.
    bl_label = "Frame\u200b"
    bl_description = (
        "Draw a rectangle to combine selected images into one image from the current view."
    )
    bl_icon = "ops.sculpt.border_mask"
    bl_operator = FrameImages.bl_idname
    bl_keymap = image_edit_keymap(FrameImages.bl_idname, "CLICK_DRAG")


class MaskTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = MASK_TOOL_ID
    bl_label = "Mask\u200b"
    bl_description = "Hide or reveal image areas with a lasso, brush, or polyline."
    bl_icon = "ops.sculpt.lasso_mask"
    bl_operator = EditImageAlpha.bl_idname
    bl_cursor = "PAINT_CROSS"
    bl_keymap = image_edit_keymap(EditImageAlpha.bl_idname, "PRESS", "CLICK_DRAG")

    def draw_settings(context, layout, _tool):
        settings = context.scene.anyimage_settings
        layout.prop(settings, "mask_gesture")
        layout.prop(settings, "mask_mode", expand=True, icon_only=True)
        if settings.mask_gesture == "BRUSH":
            layout.prop(settings, "mask_radius")


class RectifyTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = RECTIFY_TOOL_ID
    bl_label = "Rectify"
    bl_description = (
        "Select four corners of an image area to correct its perspective into a rectangle."
    )
    bl_icon = "ops.sculpt.line_project"
    bl_operator = RectifyImagePerspective.bl_idname
    bl_keymap = image_edit_keymap(RectifyImagePerspective.bl_idname, "PRESS")


class CutoutTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = SelectCutoutSelection.active_tool_id
    bl_label = "Cutout"
    bl_description = "Select an Image Empty area with a lasso or polyline and choose a mesh shape"
    bl_icon = "ops.mesh.primitive_sphere_add_gizmo"
    bl_operator = SelectCutoutSelection.bl_idname
    bl_keymap = image_edit_keymap(SelectCutoutSelection.bl_idname, "PRESS", "CLICK_DRAG")

    def draw_settings(context, layout, _tool):
        settings = context.scene.anyimage_settings
        layout.prop(settings, "cutout_gesture")
        layout.prop(settings, "cutout_edge_length")
        layout.prop(settings, "cutout_fine_outline")
        layout.prop(settings, "cutout_alpha_threshold")
