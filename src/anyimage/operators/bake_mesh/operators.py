"""Bake the active image object into a textured static mesh."""

import bpy

from ...common.object import get_modifier_input
from .materialization import PROTOCOL_ATTRIBUTES, materialize_mesh_and_textures, mesh_bake_modifiers


class BakeMesh(bpy.types.Operator):
    bl_idname = "anyimage.bake_mesh"
    bl_label = "Bake Mesh"
    bl_description = "Apply the image geometry and materialize static textures and normals"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return getattr(context, "mode", None) == "OBJECT" and bool(mesh_bake_modifiers(getattr(context, "object", None)))

    def execute(self, context):
        obj = context.object
        depth_images = set()
        try:
            modifiers = mesh_bake_modifiers(obj)
            for modifier in modifiers:
                for socket in modifier.node_group.interface.items_tree:
                    if (socket.item_type == "SOCKET" and socket.in_out == "INPUT"
                            and socket.name == "Depth Image" and socket.socket_type == "NodeSocketImage"):
                        image = get_modifier_input(modifier, socket.identifier)
                        if image is not None:
                            depth_images.add(image)
            mesh = materialize_mesh_and_textures(context, obj)
        except (RuntimeError, ValueError, TypeError, MemoryError, ReferenceError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        obj.data = mesh
        for modifier in modifiers:
            obj.modifiers.remove(modifier)
        del obj["o_image_object"]
        for name in tuple(obj.keys()):
            if name in PROTOCOL_ATTRIBUTES:
                del obj[name]
        obj.update_tag(refresh={"DATA"})
        for image in depth_images:
            if image.users == 0:
                bpy.data.images.remove(image)
        return {"FINISHED"}
