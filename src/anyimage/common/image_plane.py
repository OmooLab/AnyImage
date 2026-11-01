"""Create rectangular image meshes and plane objects."""

import bpy

from .object import (
    blender_frame_rotation, finalize_object_result, modifier_input_identifier, set_modifier_input,
)
from .node import load_node_group
from .image import image_empty_bounds


IMAGE_PLANE_NODE_GROUP_NAME = "O Plane"


def build_image_plane_matrix(matrix_world, bounds):
    from mathutils import Matrix

    x_min, x_max, y_min, y_max = bounds
    center = ((x_min + x_max) * 0.5, (y_min + y_max) * 0.5, 0.0)
    return matrix_world @ Matrix.Translation(center) @ blender_frame_rotation().inverted()


def create_image_plane_mesh(name, bounds):
    x_min, x_max, y_min, y_max = bounds
    if x_max <= x_min or y_max <= y_min:
        raise ValueError("The plane has invalid dimensions")

    half_width = (x_max - x_min) * 0.5
    half_height = (y_max - y_min) * 0.5

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(
        (
            (-half_width, 0.0, -half_height),
            (half_width, 0.0, -half_height),
            (half_width, 0.0, half_height),
            (-half_width, 0.0, half_height),
        ),
        (),
        ((0, 1, 2, 3),),
    )
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for loop, uv in zip(
        mesh.loops,
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    ):
        uv_layer.data[loop.index].uv = uv
    return mesh


def add_image_plane_processing(
    plane_object,
    subdivisions=0,
    thickness=0.0,
):
    node_group = load_node_group(IMAGE_PLANE_NODE_GROUP_NAME)
    modifier = plane_object.modifiers.new(
        name=IMAGE_PLANE_NODE_GROUP_NAME,
        type="NODES",
    )
    modifier.node_group = node_group
    modifier.show_group_selector = False
    for name, value in (
        ("Subdivide", max(0, min(8, int(subdivisions)))),
        ("Thickness", max(0.0, float(thickness))),
    ):
        identifier = modifier_input_identifier(node_group, name)
        set_modifier_input(modifier, identifier, value)
    return modifier


def create_plane_object(context, source_object, subdivisions, material):
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
        add_image_plane_processing(plane, subdivisions=subdivisions)
        return finalize_object_result(context, source_object, plane)
    except Exception:
        if plane is not None:
            bpy.data.objects.remove(plane, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
