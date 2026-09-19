import bpy

from .common.image import is_image_empty
from .common.image_target import active_texture_node, image_edit_owner, owner_image
from .operators.upscale import upscale_output_size


class AnyImageImageMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "AnyImage"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(
            "anyimage.convert_to_plane",
            text="Convert to Plane",
            icon="IMAGE_PLANE",
        )
        layout.operator(
            "anyimage.convert_to_depth_plane",
            text="Convert to Depth Plane",
            icon="MOD_DISPLACE",
        )
        layout.operator(
            "anyimage.convert_to_relief_plane",
            text="Convert to Relief Plane",
            icon="MOD_DISPLACE",
        )
        layout.operator(
            "anyimage.convert_to_panorama",
            text="Convert to Panorama",
            icon="SPHERE",
        )
        layout.separator()
        draw_image_actions(layout, context)


class AnyImageTextureNodeMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "AnyImage"

    def draw(self, context):
        draw_image_actions(self.layout, context)


def draw_image_actions(layout, context):
    from .properties import ai_setup_label, ai_status

    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator(
        "anyimage.remove_image_background",
        text="Remove Background",
        icon="IMAGE_ALPHA",
    )
    layout.operator(
        "anyimage.upscale_image",
        text=upscale_menu_label(context),
        icon="FULLSCREEN_ENTER",
    )
    layout.separator()
    status = ai_status()
    if status["ready"]:
        layout.operator(
            "anyimage.open_ai_environment_settings",
            text="Settings",
            icon="PREFERENCES",
        )
    else:
        layout.operator(
            "anyimage.setup_ai_environment",
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
    self.layout.menu(AnyImageImageMenu.bl_idname, text="AnyImage", icon="PLUGIN")
    self.layout.separator()


def draw_texture_node_context_menu(self, context):
    if active_texture_node(context) is None:
        return
    self.layout.menu(AnyImageTextureNodeMenu.bl_idname, text="AnyImage", icon="PLUGIN")
    self.layout.separator()
