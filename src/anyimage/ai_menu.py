from . import menu
import bpy

from .common.image_target import (
    image_edit_owner,
    owner_image,
)
from .operators.ai_setup import OpenAIEnvironmentSettings, SetupAIServer
from .operators.convert_to_panorama import ConvertToPanorama
from .operators.convert_to_plane.operators import (
    ConvertToDepthPlane,
    ConvertToReliefPlane,
)
from .operators.remove_background import RemoveImageBackground
from .operators.upscale import UpscaleImage
from .operators.upscale import upscale_output_size


def draw_conversions(layout, context):
    menu.draw_plane(layout, context)
    layout.operator(ConvertToDepthPlane.bl_idname, icon="MOD_DISPLACE")
    layout.operator(ConvertToReliefPlane.bl_idname, icon="MOD_DISPLACE")
    layout.operator(ConvertToPanorama.bl_idname, icon="SPHERE")
    layout.separator()


class AnyImageImageMenu(menu.AnyImageImageMenu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "AnyImage"

    def draw(self, context):
        menu.draw_image_menu(self.layout, context, draw_image_actions, draw_conversions)


class AnyImageTextureNodeMenu(menu.AnyImageTextureNodeMenu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "AnyImage"

    def draw(self, context):
        draw_image_actions(self.layout, context)


class AnyImageObjectMenu(menu.AnyImageObjectMenu):
    bl_idname = "ANYIMAGE_MT_object_context"
    bl_label = "AnyImage"

    def draw(self, context):
        menu.draw_object_menu(self.layout, context, draw_image_actions)


def draw_image_actions(layout, context):
    from .ai_properties import ai_setup_label, ai_status

    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator(
        RemoveImageBackground.bl_idname,
        icon="IMAGE_ALPHA",
    )
    layout.operator(
        UpscaleImage.bl_idname,
        text=upscale_menu_label(context),
        icon="FULLSCREEN_ENTER",
    )
    menu.draw_image_actions(layout, context)
    layout.separator()
    status = ai_status()
    if status["ready"]:
        layout.operator(
            OpenAIEnvironmentSettings.bl_idname,
            icon="PREFERENCES",
        )
    else:
        layout.operator(
            SetupAIServer.bl_idname,
            text=ai_setup_label(status),
            icon="IMPORT",
        )


def upscale_menu_label(context):
    owner = image_edit_owner(context)
    if owner is None:
        return "Upscale"
    output_size = upscale_output_size(owner_image(owner))
    if output_size is None:
        return "Upscale"
    width, height = output_size
    return bpy.app.translations.pgettext_iface("Upscale ({width} × {height})").format(
        width=width,
        height=height,
    )
