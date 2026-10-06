"""Build curved depth surfaces with a symmetry modifier for tests."""

import bpy
import numpy as np
import pytest
from anyimage.common.object import modifier_input_identifier, set_modifier_input
from nodes.groups.image_depth_cutout import build_image_depth_cutout_group
from nodes.groups.image_cutout_symmetry import build_image_cutout_symmetry_group


def _set_value(obj, modifier, group):
    def setter(name, value, subtype=None):
        set_modifier_input(
            modifier,
            modifier_input_identifier(group, name, subtype=subtype),
            value,
        )
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()

    return setter


@pytest.fixture
def symmetry():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    count = 5
    z, x = np.meshgrid(
        np.linspace(-1, 1, count),
        np.linspace(-1, 1, count),
        indexing="ij",
    )
    faces = []
    for row in range(count - 1):
        for column in range(count - 1):
            start = row * count + column
            faces.extend(((start, start + 1, start + count + 1), (start, start + count + 1, start + count)))
    boundary = (np.maximum(abs(x), abs(z)) == 1).ravel()
    faces = [face for face in faces if not all(boundary[index] for index in face)]

    mesh = bpy.data.meshes.new("Curved Depth")
    mesh.from_pydata(np.column_stack((x.ravel(), np.zeros(x.size), z.ravel())), [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        row, column = divmod(loop.vertex_index, count)
        uv.data[loop.index].uv = (
            (column + 0.5) / count,
            (row + 0.5) / count,
        )
    profile = 0.3 * np.maximum(0, 1 - np.maximum(abs(x), abs(z)))
    mesh.attributes.new("o_balloon", "FLOAT", "POINT").data.foreach_set(
        "value", profile.ravel()
    )
    mesh.attributes.new("user_probe", "FLOAT", "POINT").data.foreach_set(
        "value", np.ones(x.size)
    )

    image = bpy.data.images.new("Depth", width=count, height=count, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    depth = 1 + 0.6 * x**2 + 0.3 * z**2
    pixels = np.dstack((x, -z, depth, np.ones_like(x))).astype(np.float32)
    image.pixels.foreach_set(pixels.ravel())

    obj = bpy.data.objects.new("Symmetry", mesh)
    bpy.context.collection.objects.link(obj)

    cutout_group = build_image_depth_cutout_group()
    mirror_group = build_image_cutout_symmetry_group()
    cutout = obj.modifiers.new(cutout_group.name, "NODES")
    cutout.node_group = cutout_group
    mirror = obj.modifiers.new(mirror_group.name, "NODES")
    mirror.node_group = mirror_group

    cutout_setter = _set_value(obj, cutout, cutout_group)
    mirror_setter = _set_value(obj, mirror, mirror_group)
    mirror_setter("Smooth", 0)
    for name, value in (
        ("Depth Image", image),
        ("Reference Depth", 1.45),
        ("Depth Split", 0),
        ("Boundary Smooth", 0),
    ):
        cutout_setter(name, value)
    return obj, cutout, mirror, cutout_setter, mirror_setter
