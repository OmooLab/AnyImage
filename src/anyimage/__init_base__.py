"""Register and unregister the base edition."""

import bpy

from . import keymaps
from .preferences import PreferencesBase
from .properties import SettingsBase, register_color_references, unregister_color_references

from .operators.clipboard_image import PasteClipboardImage
from .operators.bake_mesh import BakeMesh
from .operators.color_match import MatchColorReference
from .operators.convert_to_plane import ConvertToPlane
from .operators.cutout_tool import CreateCutoutShape, SelectCutoutSelection
from .operators.frame_tool import FrameImages
from .operators.mask_tool import EditImageAlpha
from .operators.rectify_tool import RectifyImagePerspective

from .menus import ImageMenuBase, ObjectMenuBase, TextureNodeMenuBase
from .color_panel import ColorMatchPanel
from .common.image import is_image_empty
from .common.image_target import is_image_object, active_texture_node
from .tools import CutoutTool, FrameTool, MaskTool, RectifyTool
from .translations import (
    build_translations,
    COMMON,
    CLIPBOARD,
    COLOR,
    FRAME,
    RECTIFY,
    MASK,
    CUTOUT,
    GEOMETRY,
)


TRANSLATIONS = build_translations(
    COMMON,
    CLIPBOARD,
    COLOR,
    FRAME,
    RECTIFY,
    MASK,
    CUTOUT,
    GEOMETRY,
)

CLASSES = (
    # Settings
    PreferencesBase,
    SettingsBase,

    # Operators
    PasteClipboardImage,
    BakeMesh,
    MatchColorReference,
    ConvertToPlane,
    CreateCutoutShape,
    SelectCutoutSelection,
    FrameImages,
    EditImageAlpha,
    RectifyImagePerspective,

    # Menus
    ImageMenuBase,
    ObjectMenuBase,
    TextureNodeMenuBase,

    # Panels
    ColorMatchPanel,
)

TOOLS = (
    (CutoutTool, {"separator": True, "group": True}),
    (FrameTool, {"after": {CutoutTool.bl_idname}, "separator": False}),
    (MaskTool, {"after": {FrameTool.bl_idname}, "separator": False}),
    (RectifyTool, {"after": {MaskTool.bl_idname}, "separator": False}),
)


def draw_image_context_menu(self, context):
    if not is_image_empty(context.object):
        return
    self.layout.menu(ImageMenuBase.bl_idname)
    self.layout.separator()


def draw_image_object_context_menu(self, context):
    if not is_image_object(getattr(context, "object", None)):
        return
    self.layout.menu(ObjectMenuBase.bl_idname)
    self.layout.separator()


def draw_texture_node_context_menu(self, context):
    if active_texture_node(context) is None:
        return
    self.layout.menu(TextureNodeMenuBase.bl_idname)
    self.layout.separator()


MENUS = (
    (bpy.types.VIEW3D_MT_object_context_menu, draw_image_context_menu),
    (bpy.types.VIEW3D_MT_object_context_menu, draw_image_object_context_menu),
    (bpy.types.OUTLINER_MT_object, draw_image_context_menu),
    (bpy.types.OUTLINER_MT_object, draw_image_object_context_menu),
    (bpy.types.NODE_MT_context_menu, draw_texture_node_context_menu),
)


def register():
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        raise RuntimeError(
            "Another AnyImage edition is already enabled. Disable it before enabling this edition."
        )
    bpy.app.translations.register(__package__, TRANSLATIONS)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(type=SettingsBase)
    for tool, options in TOOLS:
        bpy.utils.register_tool(tool, **options)
    for menu, draw in MENUS:
        menu.prepend(draw)
    keymaps.register()
    register_color_references()


def unregister():
    unregister_color_references()
    keymaps.unregister()
    for menu, draw in reversed(MENUS):
        menu.remove(draw)
    for tool, _options in reversed(TOOLS):
        bpy.utils.unregister_tool(tool)
    if hasattr(bpy.types.Scene, "anyimage_settings"):
        del bpy.types.Scene.anyimage_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    bpy.app.translations.unregister(__package__)
