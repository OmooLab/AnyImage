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


_cleanup = []


def register(classes=CLASSES, *, settings=AnyImageSettings, toolset=TOOLS, catalog=TRANSLATIONS):
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        raise RuntimeError(
            "Another AnyImage edition is already enabled. Disable it before enabling this edition."
        )
    menus = (
        (bpy.types.VIEW3D_MT_object_context_menu, draw_image_context_menu),
        (bpy.types.VIEW3D_MT_object_context_menu, draw_image_object_context_menu),
        (bpy.types.OUTLINER_MT_object, draw_image_context_menu),
        (bpy.types.OUTLINER_MT_object, draw_image_object_context_menu),
        (bpy.types.NODE_MT_context_menu, draw_texture_node_context_menu),
    )
    try:
        bpy.app.translations.register(__package__, catalog)
        _cleanup.append(lambda: bpy.app.translations.unregister(__package__))
        for cls in classes:
            bpy.utils.register_class(cls)
            _cleanup.append(lambda cls=cls: bpy.utils.unregister_class(cls))
        for tool, options in toolset:
            bpy.utils.register_tool(tool, **options)
            _cleanup.append(lambda tool=tool: bpy.utils.unregister_tool(tool))
        bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(type=settings)
        _cleanup.append(lambda: delattr(bpy.types.Scene, "anyimage_settings"))
        for menu, draw in menus:
            menu.prepend(draw)
            _cleanup.append(lambda menu=menu, draw=draw: menu.remove(draw))
        _cleanup.append(keymaps.unregister)
        keymaps.register()
        _cleanup.append(unregister_color_references)
        register_color_references()
    except Exception:
        unregister()
        raise


def unregister():
    while _cleanup:
        _cleanup.pop()()
