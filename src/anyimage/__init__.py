import bpy

from . import __init_base__ as base
from . import keymaps
from .properties import register_color_references, unregister_color_references
from .tools import tool_definitions
from .ai_menu import AnyImageImageMenu, AnyImageObjectMenu, AnyImageTextureNodeMenu
from .operators.ai_setup import CLASSES as AI_SETUP_CLASSES
from .operators.convert_to_panorama import CLASSES as PANORAMA_CLASSES
from .operators.convert_to_plane.operators import (
    GenerateDepthPlane,
    ConvertToDepthPlane,
    ConvertToReliefPlane,
)
from .operators.cutout_tool.ai_interaction import SelectCutoutSelection
from .operators.cutout_tool.operators import SelectCutoutSelection as SharedSelection
from .operators.cutout_tool.ai_operators import CutoutSelectionToShape
from .operators.remove_background import CLASSES as BACKGROUND_CLASSES
from .operators.upscale import UpscaleImage
from .panel import DangerZonePanel, ServerPanel
from .ai_preferences import AnyImagePreferences
from .ai_properties import AnyImageSettings
from .runtime import runtime
from .ai_tools import CutoutTool
from .ai_translations import TRANSLATIONS

_FULL_TYPES = {
    base.AnyImagePreferences: AnyImagePreferences,
    base.AnyImageSettings: AnyImageSettings,
    base.AnyImageImageMenu: AnyImageImageMenu,
    base.AnyImageObjectMenu: AnyImageObjectMenu,
    base.AnyImageTextureNodeMenu: AnyImageTextureNodeMenu,
    SharedSelection: SelectCutoutSelection,
}
CLASSES = (
    *(_FULL_TYPES.get(cls, cls) for cls in base.CLASSES),
    GenerateDepthPlane,
    ConvertToDepthPlane,
    ConvertToReliefPlane,
    CutoutSelectionToShape,
    *PANORAMA_CLASSES,
    *AI_SETUP_CLASSES,
    *BACKGROUND_CLASSES,
    UpscaleImage,
    ServerPanel,
    DangerZonePanel,
)


TOOLS = tool_definitions(CutoutTool)
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
        for menu, draw in base.MENUS:
            menu.prepend(draw)
            _registered_menus.append((menu, draw))
        keymaps.register()
        register_color_references()
        runtime.register()
    except Exception:
        unregister()
        raise


def unregister():
    global _registered
    if not _registered:
        return
    runtime.unregister()
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
