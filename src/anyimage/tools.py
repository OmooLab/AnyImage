import bpy

from .common.ai import draw_ai_property, draw_ai_setup
from .common.viewport import image_edit_drag_keymap, image_edit_point_keymap
from .operators.cutout_tool import SelectCutoutSelection
from .operators.frame_tool import FrameImages
from .operators.frame_tool.operators import FRAME_TOOL_ID
from .operators.mask_tool import EditImageAlpha, MASK_TOOL_ID
from .operators.rectify_tool import RectifyImagePerspective
from .operators.rectify_tool.operators import RECTIFY_TOOL_ID


class FrameTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = FRAME_TOOL_ID
    bl_label = "Frame"
    bl_description = "Draw a rectangle to combine selected images into one image from the current view."
    bl_icon = "ops.sculpt.border_mask"
    bl_operator = FrameImages.bl_idname
    bl_keymap = image_edit_drag_keymap(FrameImages.bl_idname)


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


class RectifyTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = RECTIFY_TOOL_ID
    bl_label = "Rectify"
    bl_description = "Select four corners of an image area to correct its perspective into a rectangle."
    bl_icon = "ops.sculpt.line_project"
    bl_operator = RectifyImagePerspective.bl_idname
    bl_keymap = image_edit_point_keymap(RectifyImagePerspective.bl_idname)


class CutoutTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = SelectCutoutSelection.active_tool_id
    bl_label = "Cutout"
    bl_description = "Select an Image Empty area with a lasso or polyline and choose a mesh shape"
    bl_icon = "ops.mesh.primitive_sphere_add_gizmo"
    bl_operator = SelectCutoutSelection.bl_idname
    bl_keymap = image_edit_point_keymap(SelectCutoutSelection.bl_idname)

    def draw_settings(context, layout, _tool):
        settings = context.scene.anyimage_settings
        layout.prop(settings, "cutout_gesture")
        layout.prop(settings, "cutout_edge_length")
        layout.prop(settings, "cutout_fine_outline")
        layout.prop(settings, "cutout_alpha_threshold")
        status = draw_ai_setup(layout)
        draw_ai_property(layout, settings, "cutout_generate_normal", status)


TOOLS = (
    (FrameTool, {"separator": True, "group": True}),
    (MaskTool, {"after": {FrameTool.bl_idname}, "separator": False}),
    (RectifyTool, {"after": {MaskTool.bl_idname}, "separator": False}),
    (CutoutTool, {}),
)


def register():
    for tool, options in TOOLS:
        bpy.utils.register_tool(tool, **options)


def unregister():
    for tool, _options in reversed(TOOLS):
        bpy.utils.unregister_tool(tool)
