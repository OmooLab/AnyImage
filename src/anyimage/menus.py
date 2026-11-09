import bpy
from .operators.convert_to_plane import ConvertToPlane
from .operators.color_match import MatchColorReference
from .operators.bake_mesh import BakeMesh


class ImageMenuLite(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_image_context"
    bl_label = "Any Image"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(ConvertToPlane.bl_idname, icon="IMAGE_PLANE")
        layout.operator(MatchColorReference.bl_idname, icon="COLOR")


class TextureNodeMenuLite(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_texture_node_context"
    bl_label = "Any Image"

    def draw(self, context):
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator(MatchColorReference.bl_idname, icon="COLOR")


class ObjectMenuLite(bpy.types.Menu):
    bl_idname = "ANYIMAGE_MT_object_context"
    bl_label = "Any Image"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator(BakeMesh.bl_idname, icon="MESH_DATA")
        layout.separator()
        layout.operator(MatchColorReference.bl_idname, icon="COLOR")
