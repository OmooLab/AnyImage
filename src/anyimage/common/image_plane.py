"""Build rectangular image meshes and their placement matrices."""

import bpy

IMAGE_PLANE_NODE_GROUP_NAME = "O Plane"


def build_image_plane_matrix(matrix_world, bounds):
    from mathutils import Matrix

    x_min, x_max, y_min, y_max = bounds
    center = ((x_min + x_max) * 0.5, (y_min + y_max) * 0.5, 0.0)
    plane_to_empty = Matrix((
        (1, 0, 0, 0),
        (0, 0, 1, 0),
        (0, -1, 0, 0),
        (0, 0, 0, 1),
    ))
    return matrix_world @ Matrix.Translation(center) @ plane_to_empty


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
