import bpy

from . import keymaps, tools
from .operators.clipboard_image import CLASSES as CLIPBOARD_CLASSES
from .menu import (
    AnyImageImageMenu,
    AnyImageTextureNodeMenu,
    draw_image_context_menu,
    draw_texture_node_context_menu,
)
from .operators import CLASSES as OPERATOR_CLASSES
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
    tools.register()
    bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(type=AnyImageSettings)
    bpy.types.VIEW3D_MT_object_context_menu.prepend(draw_image_context_menu)
    bpy.types.OUTLINER_MT_object.prepend(draw_image_context_menu)
    bpy.types.NODE_MT_context_menu.prepend(draw_texture_node_context_menu)
    keymaps.register()
    runtime.register()


def unregister():
    runtime.unregister()
    keymaps.unregister()
    tools.unregister()
    bpy.types.NODE_MT_context_menu.remove(draw_texture_node_context_menu)
    bpy.types.OUTLINER_MT_object.remove(draw_image_context_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_image_context_menu)
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        del bpy.types.Scene.anyimage_settings
    for class_type in reversed(CLASSES):
        bpy.utils.unregister_class(class_type)
