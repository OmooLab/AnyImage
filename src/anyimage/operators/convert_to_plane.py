import bpy

from ..common.image import image_empty_bounds, is_image_empty
from ..common.material import create_image_material
from ..common.color_image import material_color_image
from ..common.image_plane import IMAGE_PLANE_NODE_GROUP_NAME, build_image_plane_matrix, create_image_plane_mesh
from ..common.node import load_node_group
from ..common.object import finalize_object_result
from ..common.viewport import apply_material_preview


def create_plane_object(context, source_object, material):
    """Create a rectangular image object and replace its source Empty."""
    source_name = source_object.name
    bounds = image_empty_bounds(source_object)
    mesh = create_image_plane_mesh(source_name, bounds)
    plane = None
    try:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        mesh.materials.append(material)
        plane = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(plane)
        plane.matrix_world = build_image_plane_matrix(source_object.matrix_world, bounds)
        plane["o_image_object"] = True
        group = load_node_group(IMAGE_PLANE_NODE_GROUP_NAME)
        modifier = plane.modifiers.new(name=group.name, type="NODES")
        modifier.node_group = group
        modifier.show_group_selector = False
        return finalize_object_result(context, source_object, plane)
    except Exception:
        if plane is not None:
            bpy.data.objects.remove(plane, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


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
        material = None
        try:
            with material_color_image(source_object.data) as color_image:
                material = create_image_material(
                    source_object.data,
                    color_image,
                    color_is_full_source=True,
                    scene=context.scene,
                )
                create_plane_object(context, source_object, material)
        except Exception as error:
            if material is not None and material.users == 0:
                bpy.data.materials.remove(material, do_unlink=True)
            if isinstance(error, ValueError):
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}
            raise
        apply_material_preview(context)
        return {"FINISHED"}
