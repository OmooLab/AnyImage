import bpy

from .common.image_target import image_edit_owner
from .common.image import owner_image
from .operators.convert_to_plane import ConvertToPlane
from .operators.color_match import MatchColorReference
from .operators.bake_mesh import BakeMesh
from .operators.ai_setup import OpenAIEnvironmentSettings
from .operators.convert_to_panorama import ConvertToPanorama
from .operators.depth_plane import ConvertToDepthPlane, ConvertToReliefPlane
from .operators.remove_background import RemoveImageBackground
from .operators.upscale import UpscaleImage
from .operators.upscale import upscale_output_size


class ImageMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "Any Image"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(ConvertToPlane.bl_idname, icon="IMAGE_PLANE")
        layout.operator(ConvertToDepthPlane.bl_idname, icon="MOD_DISPLACE")
        layout.operator(ConvertToReliefPlane.bl_idname, icon="MOD_DISPLACE")
        layout.operator(ConvertToPanorama.bl_idname, icon="SPHERE")
        layout.separator()
        draw_image_actions(layout, context)


class TextureNodeMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "Any Image"

    def draw(self, context):
        draw_image_actions(self.layout, context)


class ObjectMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_object_context"
    bl_label = "Any Image"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(BakeMesh.bl_idname, icon="MESH_DATA")
        layout.separator()
        draw_image_actions(layout, context)


def draw_image_actions(layout, context):
    from .common.ai import draw_ai_setup

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
    layout.operator(MatchColorReference.bl_idname, icon="COLOR")
    layout.separator()
    status = draw_ai_setup(layout)
    if status["ready"]:
        layout.operator(
            OpenAIEnvironmentSettings.bl_idname,
            icon="PREFERENCES",
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
