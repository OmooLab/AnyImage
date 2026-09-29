"""Convert the active procedural Cutout into a textured static Mesh."""

import bpy

from .materialization import PROTOCOL_ATTRIBUTES, build_conversion_mesh, supports_conversion


class ConvertToMesh(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_mesh"
    bl_label = "Convert to Mesh"
    bl_description = "Apply the Cutout shape and materialize independent textures and static normals"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return getattr(context, "mode", None) == "OBJECT" and supports_conversion(getattr(context, "object", None))

    def execute(self, context):
        obj = context.object
        try:
            mesh = build_conversion_mesh(context, obj)
        except (RuntimeError, ValueError, TypeError, MemoryError, ReferenceError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        obj.data = mesh
        obj.modifiers.clear()
        for name in tuple(obj.keys()):
            if name in PROTOCOL_ATTRIBUTES:
                del obj[name]
        obj.update_tag(refresh={"DATA"})
        return {"FINISHED"}
