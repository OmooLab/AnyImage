"""Focused geometry-node checks for Depth Cutout leaf construction and bridging."""

import bpy
import bmesh
import numpy as np
import pytest

from anyimage.common.object import modifier_input_identifier, set_modifier_input
from nodes.common.boundary_smoothing import boundary_influence
from nodes.common.nodes import store_float_attribute
from nodes.groups.image_depth_cutout import (
    BOUNDARY_FALLOFF_ATTRIBUTE,
    SIDE_UV_INFLUENCE_ITERATIONS,
    prepare_bridge_uv,
)
from tests.nodes.test_boundary_smoothing import boundary_neighbors
from tests.support.depth_surface import evaluated, surface


def _geometry_group(name):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    return group, source.outputs["Geometry"], output.inputs["Geometry"]


def _object(points, edges, faces, group):
    mesh = bpy.data.meshes.new("Leaf Bridge")
    mesh.from_pydata(points, edges, faces)
    obj = bpy.data.objects.new("Leaf Bridge", mesh)
    bpy.context.collection.objects.link(obj)
    obj.modifiers.new("Leaf Bridge", "NODES").node_group = group
    bpy.context.view_layer.update()
    return obj


def _evaluated_corner_uv(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return np.array([loop.uv[:] for loop in mesh.uv_layers["UVMap"].data])
    finally:
        result.to_mesh_clear()


def _bridge_uv_group(name):
    group, geometry, result = _geometry_group(name)
    geometry = store_float_attribute(
        group,
        geometry,
        BOUNDARY_FALLOFF_ATTRIBUTE,
        boundary_influence(group, iterations=SIDE_UV_INFLUENCE_ITERATIONS),
    )
    group.links.new(prepare_bridge_uv(group, geometry, 1.0), result)
    return group


def _assert_oriented_closed(faces):
    uses = {}
    for face in faces:
        for start, end in zip(face, (*face[1:], face[0])):
            uses.setdefault(tuple(sorted((start, end))), []).append((start, end))
    assert uses
    assert all(len(edges) == 2 and edges[0] == edges[1][::-1] for edges in uses.values())


def _assert_positive_face_areas(points, faces):
    for face in faces:
        origin = points[face[0]]
        area = sum(
            np.linalg.norm(np.cross(points[face[i]] - origin, points[face[i + 1]] - origin))
            for i in range(1, len(face) - 1)
        ) / 2
        assert area > 1e-10


def test_leaf_uv_pull_fades_through_four_boundary_rings_and_preserves_the_core():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    size = 13
    points = np.array([(x, 0.0, z) for z in range(size) for x in range(size)], dtype=float)
    faces = []
    for z in range(size - 1):
        for x in range(size - 1):
            a = z * size + x
            faces.append((a, a + 1, a + size + 1, a + size))
    obj = _object(points, [], faces, _bridge_uv_group("Leaf Boundary UV Pull"))
    uv_layer = obj.data.uv_layers.new(name="UVMap")
    original = np.empty((len(obj.data.loops), 2), dtype=float)
    for loop in obj.data.loops:
        point = obj.data.vertices[loop.vertex_index].co
        value = (point.x / (size - 1), point.z / (size - 1))
        uv_layer.data[loop.index].uv = value
        original[loop.index] = value
    obj.data.update()
    bpy.context.view_layer.update()

    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        pulled = np.array([item.uv[:] for item in mesh.uv_layers["UVMap"].data])
        vertices = np.array([loop.vertex_index for loop in mesh.loops])
        coordinates = points[vertices][:, (0, 2)]
        boundary = np.any((coordinates == 0) | (coordinates == size - 1), axis=1)
        core = np.all((coordinates >= 5) & (coordinates <= size - 6), axis=1)
        assert np.max(np.abs(pulled[boundary] - original[boundary])) > 1e-4
        np.testing.assert_allclose(pulled[core], original[core], atol=1e-7)
        assert np.all(pulled[coordinates[:, 0] == 0, 0] >= -1e-7)
        assert np.all(pulled[coordinates[:, 0] == size - 1, 0] <= 1.0 + 1e-7)
        assert np.all(pulled[coordinates[:, 1] == 0, 1] >= -1e-7)
        assert np.all(pulled[coordinates[:, 1] == size - 1, 1] <= 1.0 + 1e-7)
    finally:
        result.to_mesh_clear()


def test_depth_cutout_bridge_preserves_topology_and_side_uv():
    obj, set_value = surface(step=0, resolution=8)
    set_value("Boundary Smooth", 0)
    front, front_faces = evaluated(obj)
    boundary = boundary_neighbors(front_faces)
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary.values()) // 2
    set_value("Thickness", 0.2)
    solid_uv = _evaluated_corner_uv(obj)
    points, solid_faces = evaluated(obj)

    assert len(points) == 2 * len(front) + len(boundary)
    assert len(solid_faces) == 2 * len(front_faces) + 2 * boundary_edge_count
    _assert_oriented_closed(solid_faces)
    solid_face_uv = solid_uv.reshape(-1, 4, 2)
    assert np.all(solid_face_uv >= -1e-6)
    assert np.all(solid_face_uv <= 1.0 + 1e-6)
    side_uv = solid_face_uv[-2 * boundary_edge_count:]
    assert len(side_uv) == 2 * boundary_edge_count
    side_areas = np.abs(
        np.sum(
            side_uv[:, :, 0] * np.roll(side_uv[:, :, 1], -1, axis=1)
            - side_uv[:, :, 1] * np.roll(side_uv[:, :, 0], -1, axis=1),
            axis=1,
        )
    ) / 2
    assert np.all(side_areas > 1e-10)


@pytest.mark.parametrize("boundary", ("split", "limit"))
def test_depth_cutout_bridge_closes_generated_boundaries(boundary):
    obj, set_value = surface(step=6, resolution=8)
    if boundary == "split":
        set_value("Depth Split", 0.5)
    else:
        set_value("Depth Limit", 2.0)
    front, front_faces = evaluated(obj)
    boundary_point_count = len(boundary_neighbors(front_faces))
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.2)
    points, faces = evaluated(obj)
    assert len(points) <= 2 * len(front) + boundary_point_count
    assert len(faces) == 2 * len(front_faces) + 2 * boundary_edge_count
    _assert_oriented_closed(faces)


def test_depth_cutout_bridge_closes_hole_boundaries():
    obj, set_value = surface(step=0, resolution=10)
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    center = [
        face for face in mesh.faces
        if 0.75 < face.calc_center_median().x < 1.25
        and 0.3 < face.calc_center_median().z < 0.7
    ]
    bmesh.ops.delete(mesh, geom=center, context="FACES")
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    bpy.context.view_layer.update()

    front, front_faces = evaluated(obj)
    boundary_point_count = len(boundary_neighbors(front_faces))
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.2)
    points, faces = evaluated(obj)
    assert len(points) == 2 * len(front) + boundary_point_count
    assert len(faces) == 2 * len(front_faces) + 2 * boundary_edge_count
    _assert_oriented_closed(faces)


def test_depth_cutout_bridge_scales_beyond_4096_source_points():
    obj, set_value = surface(step=0, resolution=46)
    front, front_faces = evaluated(obj)
    assert len(front) > 4096
    boundary_point_count = len(boundary_neighbors(front_faces))
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.02)
    points, faces = evaluated(obj)
    assert len(points) == 2 * len(front) + boundary_point_count
    assert len(faces) == 2 * len(front_faces) + 2 * boundary_edge_count
    _assert_oriented_closed(faces)


# Cover every pair of controls without repeating all twelve combinations.
@pytest.mark.parametrize("mode,boundary_smooth,rear_smooth", [
    (0, 0, 0), (0, 4, 8), (0, 16, 0),
    (1, 0, 8), (1, 4, 0), (1, 16, 8),
])
def test_depth_cutout_leaf_controls_preserve_valid_solid(mode, boundary_smooth, rear_smooth):
    obj, set_value = surface(step=0, resolution=5)
    profile = obj.data.attributes.new("o_balloon", "FLOAT", "POINT")
    profile.data.foreach_set("value", np.ones(len(obj.data.vertices), dtype=np.float32))
    modifier = obj.modifiers[0]
    set_modifier_input(
        modifier,
        modifier_input_identifier(modifier.node_group, "Mode"),
        mode,
    )
    set_modifier_input(
        modifier,
        modifier_input_identifier(
            modifier.node_group, "Thickness", subtype="NONE" if mode == 0 else "DISTANCE",
        ),
        0.2,
    )
    set_value("Boundary Smooth", boundary_smooth)
    set_value("Rear Smooth", rear_smooth)
    points, faces = evaluated(obj)
    assert np.isfinite(points).all()
    _assert_oriented_closed(faces)
    _assert_positive_face_areas(points, faces)

    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        assert "UVMap" in mesh.uv_layers
        assert "o_balloon" in mesh.attributes
        assert "o_normal_reduction" in mesh.attributes
    finally:
        result.to_mesh_clear()


def test_depth_cutout_shares_smoothing_and_side_construction():
    from nodes.groups.image_depth_cutout import build_image_depth_cutout_group

    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = build_image_depth_cutout_group()
    for kind in ("GeometryNodeRepeatOutput", "GeometryNodeExtrudeMesh"):
        assert sum(node.bl_idname == kind for node in group.nodes) == 1
    for name in ("_o_side_base_uv", "_o_side_top_uv"):
        assert sum(
            node.bl_idname == "GeometryNodeStoreNamedAttribute"
            and node.inputs["Name"].default_value == name
            for node in group.nodes
        ) == 1
