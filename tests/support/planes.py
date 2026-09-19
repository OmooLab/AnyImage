"""Evaluate complete-image projection and rectangular surface topology."""

import bpy
import numpy as np
import pytest

from nodes.groups.image_plane import build_image_plane_group
from nodes.groups.image_depth_plane import build_image_depth_plane_group
from nodes.groups.image_relief_plane import build_image_relief_plane_group


@pytest.fixture
def surface():
    return create_surface("DEPTH")


@pytest.fixture
def relief():
    return create_surface("RELIEF")


def create_surface(plane_type):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    plane = build_image_plane_group()
    builder = build_image_depth_plane_group if plane_type == "DEPTH" else build_image_relief_plane_group
    group = builder(plane)
    mesh = bpy.data.meshes.new("Rectangle")
    mesh.from_pydata([(-2, 0, -1), (2, 0, -1), (2, 0, 1), (-2, 0, 1)], [], [(0, 1, 2, 3)])
    material = bpy.data.materials.new("Image")
    mesh.materials.append(material)
    obj = bpy.data.objects.new("Surface", mesh)
    bpy.context.collection.objects.link(obj)
    modifier = obj.modifiers.new("Surface", "NODES")
    modifier.node_group = group
    image = bpy.data.images.new("Camera", width=16, height=8, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    yy, xx = np.mgrid[:8, :16]
    # Camera principal point is deliberately off center; Y points down.
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 0] = ((xx + 0.5) - 5) / 4
    pixels[..., 1] = (3 - (yy + 0.5)) / 4
    pixels[..., 2] = 2 + (xx + 0.5) / 16
    pixels[..., 3] = 1
    image.pixels.foreach_set(pixels.ravel())
    inputs = {item.name: item for item in group.interface.items_tree
              if item.item_type == "SOCKET" and item.in_out == "INPUT"}
    def set_value(name, value):
        modifier[inputs[name].identifier] = value
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()

    for name, value in (("Subdivide", 2), ("Depth Image", image),
                        ("Uniform Scale", 0.5), ("Reference Depth", 1.2),
                        ("Depth Scale", 0.0), ("Thickness", 0.0)):
        set_value(name, value)
    if "Depth Offset" in inputs:
        set_value("Depth Offset", 0.0)
    if "Boundary Smooth" in inputs:
        set_value("Boundary Smooth", 0)
    if "Depth Split" in inputs:
        set_value("Depth Split", 0.0)
    return obj, set_value, plane, inputs, image


def evaluated(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return (
            np.array([v.co[:] for v in mesh.vertices]),
            [tuple(face.vertices) for face in mesh.polygons],
            np.array([value.uv[:] for value in mesh.uv_layers["UVMap"].data]) if mesh.uv_layers else np.empty((0, 2)),
            [material.name if material else None for material in mesh.materials],
            [face.material_index for face in mesh.polygons],
            [attr.name for attr in mesh.attributes],
        )
    finally:
        result.to_mesh_clear()
