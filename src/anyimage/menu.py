import bpy
from .operators.convert_to_plane.plane import ConvertToPlane
from .operators.color_match import MatchColorReference
from .operators.bake_mesh import BakeMesh


def draw_image_actions(layout, context):
    layout.operator(MatchColorReference.bl_idname, icon="COLOR")


def draw_plane(layout, context):
    layout.operator(ConvertToPlane.bl_idname, icon="IMAGE_PLANE")


def draw_image_menu(layout, context, actions=draw_image_actions, conversions=draw_plane):
    layout.operator_context = "INVOKE_DEFAULT"
    conversions(layout, context)
    actions(layout, context)


def draw_object_menu(layout, context, actions=draw_image_actions):
    layout.operator_context = "INVOKE_DEFAULT"
    layout.operator(BakeMesh.bl_idname, icon="MESH_DATA")
    layout.separator()
    actions(layout, context)


class AnyImageImageMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "AnyImage Base"

    def draw(self, context):
        draw_image_menu(self.layout, context)


class AnyImageTextureNodeMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "AnyImage Base"

    def draw(self, context):
        self.layout.operator_context = "INVOKE_DEFAULT"
        draw_image_actions(self.layout, context)


class AnyImageObjectMenu(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_object_context"
    bl_label = "AnyImage Base"

    def draw(self, context):
        draw_object_menu(self.layout, context)
