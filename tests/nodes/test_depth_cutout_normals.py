"""Check island directions and boundary stabilization for Depth Cutout."""

import bpy
import numpy as np
import pytest

from nodes.common.nodes import store_vector_attribute
from nodes.groups.image_depth_cutout import (
    BOUNDARY_FALLOFF_ATTRIBUTE,
    build_normal_direction,
    build_smoothed_normals,
)


def normal_samples(normal_bias, *, iterations=128, boundary=1.0, profile=0.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    points, faces = [], []
    for island in range(2):
        start = len(points)
        for row in range(7):
            for column in range(7):
                x, z = column / 6, row / 6
                y = 0.2 * np.sin(5 * x + 3 * z) + island * 0.7 * x
                points.append((x + island * 3, y, z))
        for row in range(6):
            for column in range(6):
                index = start + row * 7 + column
                faces.append((index, index + 1, index + 8, index + 7))
    mesh = bpy.data.meshes.new("Normal Islands")
    mesh.from_pydata(points, [], faces)
    mesh.attributes.new(BOUNDARY_FALLOFF_ATTRIBUTE, "FLOAT", "POINT").data.foreach_set(
        "value", np.full(len(points), boundary),
    )
    obj = bpy.data.objects.new("Normal Islands", mesh)
    bpy.context.collection.objects.link(obj)
    group = bpy.data.node_groups.new("Normal Directions", "GeometryNodeTree")
    for direction in ("INPUT", "OUTPUT"):
        group.interface.new_socket(
            name="Geometry", in_out=direction, socket_type="NodeSocketGeometry",
        )
    group.interface.new_socket(
        name="Normal Bias", in_out="INPUT", socket_type="NodeSocketFloat",
    ).default_value = normal_bias
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    smoothed, average = build_smoothed_normals(group)
    blur = next(node for node in group.nodes if node.bl_idname == "GeometryNodeBlurAttribute")
    assert blur.inputs["Iterations"].default_value == 128
    blur.inputs["Iterations"].default_value = iterations
    normal = group.nodes.new("GeometryNodeInputNormal").outputs[0]
    fields = {
        "raw": normal,
        "smoothed": smoothed,
        "average": average,
        "direction": build_normal_direction(group, source, smoothed, average, profile),
    }
    geometry = source.outputs["Geometry"]
    for name, field in fields.items():
        geometry = store_vector_attribute(group, geometry, name, field)
    group.links.new(geometry, output.inputs["Geometry"])
    obj.modifiers.new("Normal Directions", "NODES").node_group = group
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = result.to_mesh()
    try:
        return {
            name: np.array([item.vector[:] for item in evaluated.attributes[name].data])
            for name in fields
        }
    finally:
        result.to_mesh_clear()


def test_normal_bias_zero_uses_each_raw_island_average_independent_of_blur():
    direct = normal_samples(0.0, iterations=0)
    blurred = normal_samples(0.0)
    np.testing.assert_array_equal(direct["direction"], blurred["direction"])
    for indices in (slice(0, 49), slice(49, 98)):
        total = direct["raw"][indices].sum(axis=0)
        expected = np.broadcast_to(total / np.linalg.norm(total), (49, 3))
        np.testing.assert_allclose(direct["direction"][indices], expected, atol=1e-6)
    assert np.linalg.norm(direct["direction"][0] - direct["direction"][49]) > 0.1


@pytest.mark.parametrize("normal_bias", (-0.0001, 0.0001))
def test_normal_bias_near_zero_keeps_its_continuous_blend(normal_bias):
    values = normal_samples(normal_bias, iterations=0)
    delta = np.linalg.norm(values["direction"] - values["average"], axis=1)
    assert 1e-6 < delta.max() < 1e-3


@pytest.mark.parametrize("boundary,profile", [(0.0, 0.0), (1.0, 0.0), (0.5, 0.4)])
def test_boundary_normal_blend_fades_without_replacing_the_profile(boundary, profile):
    values = normal_samples(-1.0, boundary=boundary, profile=profile)
    weight = profile + (1 - profile) * boundary * 0.25
    expected = (1 - weight) * values["smoothed"] + weight * values["average"]
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    np.testing.assert_allclose(values["direction"], expected, atol=1e-6)


@pytest.mark.parametrize("normal_bias", (-2.0, 2.0))
def test_normal_bias_endpoints_preserve_the_shifted_direction(normal_bias):
    values = normal_samples(normal_bias, iterations=0, boundary=0.5, profile=0.4)
    weight = 0.4 + 0.6 * 0.5 * 0.25
    blend = weight + (1 - weight) * (normal_bias + 1)
    expected = values["smoothed"] + (values["average"] - values["smoothed"]) * blend
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    np.testing.assert_allclose(values["direction"], expected, atol=1e-6)
