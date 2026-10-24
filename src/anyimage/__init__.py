from . import __init_base__ as base
from .__init_base__ import unregister
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


def register():
    base.register(
        CLASSES,
        settings=AnyImageSettings,
        toolset=tool_definitions(CutoutTool),
        catalog=TRANSLATIONS,
    )
    try:
        runtime.register()
        base._cleanup.append(runtime.unregister)
    except Exception:
        runtime.unregister()
        base.unregister()
        raise
