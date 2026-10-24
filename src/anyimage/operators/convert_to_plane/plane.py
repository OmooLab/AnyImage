import bpy

from ...common.image import is_image_empty
from ...common.material import create_image_material
from ...common.color_image import material_color_image, require_static_color_image
from .image_plane import create_plane_object


class ConvertToPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_plane"
    bl_label = "Convert to Plane"
    bl_description = "Convert the complete Image Empty into a rectangular plane"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_image_empty(context.object)

    def execute(self, context):
        source_object = context.object
        try:
            require_static_color_image(source_object.data)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        material = None
        try:
            with material_color_image(source_object.data) as color_image:
                material = create_image_material(
                    source_object.data,
                    color_image,
                    scene=context.scene,
                )
                create_plane_object(context, source_object, 0, material)
        except Exception as error:
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)
            if isinstance(error, ValueError):
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}
            raise
        return {"FINISHED"}
