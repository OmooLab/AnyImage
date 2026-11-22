"""Convert a static Image Empty into the scene World."""

import bpy

from ..common.color_image import configure_material_color_image, material_color_image
from ..common.image import is_image_empty, is_static_image
from ..common.panorama import create_panorama_world, panorama_crop_bounds, report_panorama_crop


class ConvertToWorld(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_world"
    bl_label = "Convert to World"
    bl_description = "Use the Image Empty as the scene environment"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return is_image_empty(obj) and is_static_image(obj.data) and obj.data.size[0] >= 2

    def execute(self, context):
        source = context.object
        try:
            bounds = panorama_crop_bounds(*source.data.size)
            report_panorama_crop(self, source.data.size, bounds)
            with material_color_image(source.data, bounds=bounds) as color:
                configure_material_color_image(color, context.scene)
                previous_world = context.scene.world
                world = create_panorama_world(source.data, color)
                try:
                    context.scene.world = world
                    bpy.data.objects.remove(source, do_unlink=True)
                except Exception:
                    context.scene.world = previous_world
                    bpy.data.worlds.remove(world)
                    raise
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}
