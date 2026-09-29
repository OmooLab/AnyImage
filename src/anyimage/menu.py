import bpy

from .common.image import is_image_empty
from .common.image_target import (
    active_texture_node,
    image_edit_owner,
    is_image_object,
    owner_image,
)
from .operators.ai_setup import OpenAIEnvironmentSettings, SetupAIEnvironment
from .operators.convert_to_panorama import ConvertToPanorama
from .operators.color_reference import MatchColorReference
from .operators.bake_mesh import BakeMesh
from .operators.convert_to_plane import (
    ConvertToDepthPlane,
    ConvertToPlane,
    ConvertToReliefPlane,
)
from .operators.remove_background import RemoveImageBackground
from .operators.upscale import UpscaleImage
from .operators.upscale import upscale_output_size


class AnyImageImageMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "AnyImage"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(
            ConvertToPlane.bl_idname,
            icon="IMAGE_PLANE",
        )
        layout.operator(
            ConvertToDepthPlane.bl_idname,
            icon="MOD_DISPLACE",
        )
        layout.operator(
            ConvertToReliefPlane.bl_idname,
            icon="MOD_DISPLACE",
        )
        layout.operator(
            ConvertToPanorama.bl_idname,
            icon="SPHERE",
        )
        layout.separator()
        draw_image_actions(layout, context)


class AnyImageTextureNodeMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "AnyImage"

    def draw(self, context):
        draw_image_actions(self.layout, context)


class AnyImageObjectMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_object_context"
    bl_label = "AnyImage"

    def draw(self, context):
        if BakeMesh.poll(context):
            self.layout.operator(BakeMesh.bl_idname, icon="MESH_DATA")
            self.layout.separator()
        draw_image_actions(self.layout, context)


def draw_image_actions(layout, context):
    from .properties import ai_setup_label, ai_status

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
    status = ai_status()
    if status["ready"]:
        layout.operator(
            OpenAIEnvironmentSettings.bl_idname,
            icon="PREFERENCES",
        )
    else:
        layout.operator(
            SetupAIEnvironment.bl_idname,
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
    return f"Upscale ({width} × {height})"


def draw_image_context_menu(self, context):
    if not is_image_empty(context.object):
        return
    self.layout.menu(AnyImageImageMenu.bl_idname)
    self.layout.separator()


def draw_image_object_context_menu(self, context):
    if not is_image_object(getattr(context, "object", None)):
        return
    self.layout.menu(AnyImageObjectMenu.bl_idname)
    self.layout.separator()


def draw_texture_node_context_menu(self, context):
    if active_texture_node(context) is None:
        return
    self.layout.menu(AnyImageTextureNodeMenu.bl_idname)
    self.layout.separator()
