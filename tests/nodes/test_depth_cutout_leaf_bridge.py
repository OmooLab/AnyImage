"""Focused geometry-node checks for Depth Cutout leaf construction and bridging."""

import bpy
import bmesh
import numpy as np
import pytest

from anyimage.common.object import modifier_input_identifier, set_modifier_input
from tests.support.boundary import boundary_neighbors
from tests.support.depth_surface import evaluated, surface


def _evaluated_corner_uv(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return np.array([loop.uv[:] for loop in mesh.uv_layers["UVMap"].data])
    finally:
        result.to_mesh_clear()


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
    from nodes.O_AnyImage.O_AnyImage.geometry.o_image_depth_cutout import OImageDepthCutout

    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = OImageDepthCutout.create_group()
    for kind in ("GeometryNodeRepeatOutput", "GeometryNodeExtrudeMesh"):
        assert sum(node.bl_idname == kind for node in group.nodes) == 1
    for name in ("_o_side_base_uv", "_o_side_top_uv"):
        assert sum(
            node.bl_idname == "GeometryNodeStoreNamedAttribute"
            and node.inputs["Name"].default_value == name
            for node in group.nodes
        ) == 1
