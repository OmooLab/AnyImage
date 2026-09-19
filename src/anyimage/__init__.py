import bpy

from .operators import clipboard_image
from .operators.clipboard_image import CLASSES as CLIPBOARD_CLASSES
from .menu import (
    AnyImageImageMenu,
    AnyImageTextureNodeMenu,
    draw_image_context_menu,
    draw_texture_node_context_menu,
)
from .operators import CLASSES as OPERATOR_CLASSES
from .operators.cutout_tool import CutoutTool
from .operators.frame_tool import FrameTool
from .operators.mask_tool import MaskTool
from .operators.rectify_tool import RectifyTool
from .panel import ServerPanel
from .preferences import AnyImagePreferences
from .properties import AnyImageSettings
from .runtime import runtime


CLASSES = (
    AnyImagePreferences,
    AnyImageSettings,
    *CLIPBOARD_CLASSES,
    *OPERATOR_CLASSES,
    AnyImageImageMenu,
    AnyImageTextureNodeMenu,
    ServerPanel,
)


def register():
    for class_type in CLASSES:
        bpy.utils.register_class(class_type)
    bpy.utils.register_tool(FrameTool, separator=True, group=True)
    bpy.utils.register_tool(
        MaskTool,
        after={FrameTool.bl_idname},
        separator=False,
    )
    bpy.utils.register_tool(
        RectifyTool,
        after={MaskTool.bl_idname},
        separator=False,
    )
    bpy.utils.register_tool(CutoutTool)
    bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(type=AnyImageSettings)
    bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_image_context_menu)
    bpy.types.OUTLINER_MT_object.prepend(draw_image_context_menu)
    bpy.types.NODE_MT_context_menu.prepend(draw_texture_node_context_menu)
    clipboard_image.register_keymaps()
    runtime.register()


def unregister():
    runtime.unregister()
    clipboard_image.unregister_keymaps()
    bpy.utils.unregister_tool(CutoutTool)
    bpy.utils.unregister_tool(RectifyTool)
    bpy.utils.unregister_tool(MaskTool)
    bpy.utils.unregister_tool(FrameTool)
    bpy.types.NODE_MT_context_menu.remove(draw_texture_node_context_menu)
    bpy.types.OUTLINER_MT_object.remove(draw_image_context_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_image_context_menu)
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        del bpy.types.Scene.anyimage_settings
    for class_type in reversed(CLASSES):
        bpy.utils.unregister_class(class_type)
