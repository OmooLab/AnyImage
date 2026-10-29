"""Register one edition and release only the resources it owns."""

import bpy

from . import keymaps
from .tools import TOOLS
from .translations import TRANSLATIONS
from .operators.clipboard_image import CLASSES as CLIPBOARD_CLASSES
from .menu import (
    AnyImageImageMenu,
    AnyImageObjectMenu,
    AnyImageTextureNodeMenu,
)
from .image_menu import (
    draw_image_context_menu,
    draw_image_object_context_menu,
    draw_texture_node_context_menu,
)
from .operators import CLASSES as OPERATOR_CLASSES
from .color_panel import ColorMatchPanel
from .preferences import AnyImagePreferences
from .properties import AnyImageSettings, register_color_references, unregister_color_references


CLASSES = (
    AnyImagePreferences,
    AnyImageSettings,
    *CLIPBOARD_CLASSES,
    *OPERATOR_CLASSES,
    AnyImageImageMenu,
    AnyImageObjectMenu,
    AnyImageTextureNodeMenu,
    ColorMatchPanel,
)


MENUS = (
    (bpy.types.VIEW3D_MT_object_context_menu, draw_image_context_menu),
    (bpy.types.VIEW3D_MT_object_context_menu, draw_image_object_context_menu),
    (bpy.types.OUTLINER_MT_object, draw_image_context_menu),
    (bpy.types.OUTLINER_MT_object, draw_image_object_context_menu),
    (bpy.types.NODE_MT_context_menu, draw_texture_node_context_menu),
)

_registered = False
_registered_classes = []
_registered_tools = []
_registered_menus = []


def register():
    global _registered
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        raise RuntimeError(
            "Another AnyImage edition is already enabled. Disable it before enabling this edition."
        )
    bpy.app.translations.register(__package__, TRANSLATIONS)
    _registered = True
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        for tool, options in TOOLS:
            bpy.utils.register_tool(tool, **options)
            _registered_tools.append(tool)
        bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(type=AnyImageSettings)
        for menu, draw in MENUS:
            menu.prepend(draw)
            _registered_menus.append((menu, draw))
        keymaps.register()
        register_color_references()
    except Exception:
        unregister()
        raise


def unregister():
    global _registered
    if not _registered:
        return
    unregister_color_references()
    keymaps.unregister()
    for menu, draw in reversed(_registered_menus):
        menu.remove(draw)
    _registered_menus.clear()
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        del bpy.types.Scene.anyimage_settings
    for tool in reversed(_registered_tools):
        bpy.utils.unregister_tool(tool)
    _registered_tools.clear()
    for cls in reversed(_registered_classes):
        bpy.utils.unregister_class(cls)
    _registered_classes.clear()
    bpy.app.translations.unregister(__package__)
    _registered = False
