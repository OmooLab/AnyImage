import bpy
from ...common.object import blender_frame_rotation
from .geometry import crop_plane_bounds
from .shape import BALLOON_ATTRIBUTE_NAME


def _cutout_world_matrix(source_matrix, crop_center):
    from mathutils import Matrix

    center_x, center_y = (float(value) for value in crop_center)
    return (
        source_matrix
        @ Matrix.Translation((center_x, center_y, 0.0))
        @ blender_frame_rotation().inverted()
    )


def _assign_uv(mesh, uv):
    import numpy as np

    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    source_uv = np.asarray(uv, dtype=np.float32)
    loop_uv = source_uv[loop_vertices]
    uv_layer.data.foreach_set("uv", loop_uv.ravel())


def _assign_float_point_attribute(mesh, name, values):
    import numpy as np

    attribute = mesh.attributes.new(name=name, type="FLOAT", domain="POINT")
    attribute.data.foreach_set("value", np.asarray(values, dtype=np.float32))


def create_cutout_mesh(context, source_object, content_bounds, base_shape, material):
    import numpy as np

    bounds = crop_plane_bounds(source_object, content_bounds, tuple(source_object.data.size))
    crop_center = ((bounds[0] + bounds[1]) * 0.5, (bounds[2] + bounds[3]) * 0.5)
    source_name = source_object.name
    mesh = bpy.data.meshes.new(source_name)
    mesh_object = None
    try:
        mesh.from_pydata(np.asarray(base_shape.vertices).tolist(), [], base_shape.faces)
        for face in mesh.polygons:
            face.use_smooth = True
        _assign_uv(mesh, base_shape.uv)
        _assign_float_point_attribute(mesh, BALLOON_ATTRIBUTE_NAME, base_shape.balloon)
        mesh.materials.append(material)
        mesh.update()
        mesh_object = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(mesh_object)
        mesh_object.matrix_world = _cutout_world_matrix(source_object.matrix_world, crop_center)
        mesh_object["o_image_object"] = True
        return mesh_object
    except Exception:
        if mesh_object is not None:
            bpy.data.objects.remove(mesh_object, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
