"""Focused geometry-node checks for Depth Cutout leaf construction and bridging."""

import bpy
import bmesh
import numpy as np
import pytest

from anyimage.common.object import modifier_input_identifier, set_modifier_input
from nodes.common.boundary_smoothing import smooth_cut_boundary
from tests.nodes.test_boundary_smoothing import boundary_neighbors
from tests.support.depth_surface import assert_closed, evaluated, surface


def _geometry_group(name):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    return group, source.outputs["Geometry"], output.inputs["Geometry"]


def _smoothing_group(name, *, joined):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    iterations = group.interface.new_socket(
        name="Boundary Smooth", in_out="INPUT", socket_type="NodeSocketInt",
    )
    iterations.default_value = 16
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    index = group.nodes.new("GeometryNodeInputIndex")
    save_index = group.nodes.new("GeometryNodeStoreNamedAttribute")
    save_index.data_type, save_index.domain = "INT", "POINT"
    save_index.inputs["Name"].default_value = "source_index"
    group.links.new(source.outputs["Geometry"], save_index.inputs["Geometry"])
    group.links.new(index.outputs["Index"], save_index.inputs["Value"])
    geometry = save_index.outputs["Geometry"]
    offset = group.nodes.new("ShaderNodeCombineXYZ")
    offset.inputs["Y"].default_value = -0.5

    def mark(leaf, value):
        node = group.nodes.new("GeometryNodeStoreNamedAttribute")
        node.data_type, node.domain = "FLOAT", "POINT"
        node.inputs["Name"].default_value = "leaf"
        node.inputs["Value"].default_value = value
        group.links.new(leaf, node.inputs["Geometry"])
        return node.outputs["Geometry"]

    raw_front = mark(geometry, 0.0)
    rear = group.nodes.new("GeometryNodeSetPosition")
    group.links.new(geometry, rear.inputs["Geometry"])
    group.links.new(offset.outputs["Vector"], rear.inputs["Offset"])
    flipped = group.nodes.new("GeometryNodeFlipFaces")
    group.links.new(rear.outputs["Geometry"], flipped.inputs["Mesh"])
    raw_rear = mark(flipped.outputs["Mesh"], 1.0)

    if joined:
        leaves = group.nodes.new("GeometryNodeJoinGeometry")
        group.links.new(raw_front, leaves.inputs["Geometry"])
        group.links.new(raw_rear, leaves.inputs["Geometry"])
        result = smooth_cut_boundary(group, leaves.outputs["Geometry"])
    else:
        front = smooth_cut_boundary(group, raw_front)
        rear_smoothed = smooth_cut_boundary(group, raw_rear)
        leaves = group.nodes.new("GeometryNodeJoinGeometry")
        group.links.new(front, leaves.inputs["Geometry"])
        group.links.new(rear_smoothed, leaves.inputs["Geometry"])
        result = leaves.outputs["Geometry"]
    group.links.new(result, output.inputs["Geometry"])
    return group


def _object(points, edges, faces, group):
    mesh = bpy.data.meshes.new("Leaf Bridge")
    mesh.from_pydata(points, edges, faces)
    obj = bpy.data.objects.new("Leaf Bridge", mesh)
    bpy.context.collection.objects.link(obj)
    obj.modifiers.new("Leaf Bridge", "NODES").node_group = group
    bpy.context.view_layer.update()
    return obj


def _evaluated(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return (
            np.array([vertex.co[:] for vertex in mesh.vertices]),
            [tuple(face.vertices) for face in mesh.polygons],
            [tuple(edge.vertices) for edge in mesh.edges],
        )
    finally:
        result.to_mesh_clear()


def _evaluated_leaf_points(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        points = np.array([vertex.co[:] for vertex in mesh.vertices])
        leaf = np.array([item.value for item in mesh.attributes["leaf"].data])
        source_index = np.array([item.value for item in mesh.attributes["source_index"].data])
        leaves = []
        for value in (0.0, 1.0):
            selected = np.flatnonzero(np.isclose(leaf, value))
            order = np.argsort(source_index[selected])
            indices = source_index[selected][order]
            np.testing.assert_array_equal(indices, np.arange(len(indices)))
            leaves.append(points[selected][order])
        return leaves
    finally:
        result.to_mesh_clear()


def _face_domain_rear(name, *, flip):
    group, geometry, result = _geometry_group(name)
    position = group.nodes.new("GeometryNodeInputPosition")
    on_face = group.nodes.new("GeometryNodeFieldOnDomain")
    on_face.data_type, on_face.domain = "FLOAT_VECTOR", "FACE"
    group.links.new(position.outputs["Position"], on_face.inputs["Value"])
    set_position = group.nodes.new("GeometryNodeSetPosition")
    group.links.new(geometry, set_position.inputs["Geometry"])
    group.links.new(on_face.outputs["Value"], set_position.inputs["Offset"])
    output = set_position.outputs["Geometry"]
    if flip:
        flipped = group.nodes.new("GeometryNodeFlipFaces")
        group.links.new(output, flipped.inputs["Mesh"])
        output = flipped.outputs["Mesh"]
    group.links.new(output, result)
    return group


def _normal(points, face):
    a, b, c = points[list(face[:3])]
    value = np.cross(b - a, c - a)
    return value / np.linalg.norm(value)


def _sorted_rows(values):
    return values[np.lexsort(tuple(values[:, axis] for axis in reversed(range(values.shape[1]))))]


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


def _has_node_path(group, source, target):
    pending = [source]
    visited = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(
            link.to_node for output in node.outputs for link in output.links
        )
    return False


def test_face_domain_rear_offset_and_flip_preserve_positions():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    points = np.array([
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (3.0, 0.0, 2.0),
    ])
    faces = [(0, 1, 2), (1, 3, 2)]
    plain = _object(points, [], faces, _face_domain_rear("Rear Plain", flip=False))
    flipped = _object(points, [], faces, _face_domain_rear("Rear Flipped", flip=True))
    plain_points, plain_faces, _ = _evaluated(plain)
    flipped_points, flipped_faces, _ = _evaluated(flipped)

    centroids = np.array([points[list(face)].mean(axis=0) for face in faces])
    expected = points.copy()
    for index in range(len(points)):
        incident = [centroids[i] for i, face in enumerate(faces) if index in face]
        expected[index] += np.mean(incident, axis=0)
    np.testing.assert_allclose(plain_points, expected, atol=1e-6)
    np.testing.assert_array_equal(flipped_points, plain_points)
    for plain_face, flipped_face in zip(plain_faces, flipped_faces):
        assert np.dot(_normal(plain_points, plain_face), _normal(flipped_points, flipped_face)) < -0.999


def test_edge_extrude_top_reposition_keeps_per_point_targets():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    points = np.array([
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (2.5, 0.0, 1.0),
        (-0.5, 0.0, 1.5),
    ])
    offsets = np.array([
        (0.1, -0.4, 0.2),
        (-0.2, -0.7, 0.1),
        (0.3, -1.0, -0.2),
        (-0.1, -0.5, 0.4),
    ])
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    group, geometry, result = _geometry_group("Edge Extrude Top Reposition")
    attribute = group.nodes.new("GeometryNodeInputNamedAttribute")
    attribute.data_type = "FLOAT_VECTOR"
    attribute.inputs["Name"].default_value = "target_position"
    extrude = group.nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "EDGES"
    extrude.inputs["Offset"].default_value = (0.0, -1.0, 0.0)
    group.links.new(geometry, extrude.inputs["Mesh"])
    set_position = group.nodes.new("GeometryNodeSetPosition")
    group.links.new(extrude.outputs["Mesh"], set_position.inputs["Geometry"])
    group.links.new(extrude.outputs["Top"], set_position.inputs["Selection"])
    group.links.new(attribute.outputs["Attribute"], set_position.inputs["Position"])
    top = group.nodes.new("GeometryNodeSeparateGeometry")
    top.domain = "EDGE"
    group.links.new(set_position.outputs["Geometry"], top.inputs["Geometry"])
    group.links.new(extrude.outputs["Top"], top.inputs["Selection"])
    group.links.new(top.outputs["Selection"], result)

    obj = _object(points, edges, [], group)
    target = obj.data.attributes.new("target_position", "FLOAT_VECTOR", "POINT")
    target.data.foreach_set("vector", (points + offsets).ravel())
    obj.data.update()
    bpy.context.view_layer.update()
    result_points, _, result_edges = _evaluated(obj)
    assert len(result_edges) == len(edges)
    np.testing.assert_allclose(
        _sorted_rows(result_points), _sorted_rows(points + offsets), atol=1e-6,
    )


def test_depth_cutout_bridge_matches_source_leaf_topology():
    obj, set_value = surface(step=0, resolution=8)
    front, front_faces = evaluated(obj)
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.2)
    points, faces = evaluated(obj)

    assert len(points) == 2 * len(front)
    assert len(faces) == 2 * len(front_faces) + boundary_edge_count
    assert_closed(faces)
    _assert_oriented_closed(faces)


def test_depth_cutout_uses_preflipped_leaves_and_one_shared_repeat():
    obj, _set_value = surface(step=0, resolution=4)
    group = obj.modifiers[0].node_group
    repeat_inputs = [node for node in group.nodes if node.bl_idname == "GeometryNodeRepeatInput"]
    repeat_outputs = [node for node in group.nodes if node.bl_idname == "GeometryNodeRepeatOutput"]
    flips = [node for node in group.nodes if node.bl_idname == "GeometryNodeFlipFaces"]
    separates = [node for node in group.nodes if node.bl_idname == "GeometryNodeSeparateGeometry"]
    extrudes = [node for node in group.nodes if node.bl_idname == "GeometryNodeExtrudeMesh"]
    merges = [node for node in group.nodes if node.bl_idname == "GeometryNodeMergeByDistance"]
    stored_names = {
        node.inputs["Name"].default_value
        for node in group.nodes
        if node.bl_idname == "GeometryNodeStoreNamedAttribute"
    }
    read_names = {
        node.inputs["Name"].default_value
        for node in group.nodes
        if node.bl_idname == "GeometryNodeInputNamedAttribute"
    }
    removed_names = {
        node.inputs["Name"].default_value
        for node in group.nodes
        if node.bl_idname == "GeometryNodeRemoveAttribute"
    }
    inputs = {
        item.name: item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    }
    profile_powers = [
        node for node in group.nodes
        if node.bl_idname == "ShaderNodeMath"
        and node.operation == "POWER"
        and node.inputs[1].default_value == pytest.approx(0.5)
    ]

    assert len(repeat_inputs) == len(repeat_outputs) == 1
    repeat_nodes = {
        node for node in group.nodes
        if _has_node_path(group, repeat_inputs[0], node)
        and _has_node_path(group, node, repeat_outputs[0])
    }
    assert not {
        "GeometryNodeSeparateGeometry",
        "GeometryNodeSampleNearest",
        "GeometryNodeSampleIndex",
        "GeometryNodeInputMeshEdgeNeighbors",
        "GeometryNodeInputMeshVertexNeighbors",
    } & {node.bl_idname for node in repeat_nodes}
    assert not [
        node for node in repeat_nodes
        if node.bl_idname == "GeometryNodeBlurAttribute"
        and node.data_type == "FLOAT"
    ]
    assert len(flips) == 1
    assert _has_node_path(group, flips[0], repeat_inputs[0])
    assert any(_has_node_path(group, repeat_outputs[0], node) for node in separates)
    assert any(
        _has_node_path(group, repeat_outputs[0], extrude)
        for extrude in extrudes
    )
    assert len(merges) == 1
    assert merges[0].mode == "ALL"
    assert not merges[0].inputs["Distance"].is_linked
    assert merges[0].inputs["Distance"].default_value == pytest.approx(1e-6)
    assert "_o_leaf_cut" not in stored_names | read_names
    assert "_o_cut_boundary" in stored_names
    assert "_o_boundary_smooth_weight" in stored_names & read_names
    assert {
        "_o_pinned_smooth_boundary",
        "_o_pinned_smooth_normalization",
    } <= stored_names
    assert "_o_pinned_smooth_normalization" in read_names
    assert removed_names == {"_o_depth_*", "_o_pinned_smooth_*", "_o_*"}

    for name in ("_o_boundary_smooth_weight", "_o_front_normal"):
        store = next(
            node for node in group.nodes
            if node.bl_idname == "GeometryNodeStoreNamedAttribute"
            and node.inputs["Name"].default_value == name
        )
        assert any(
            link.to_node.bl_idname == "GeometryNodeSwitch"
            and link.to_socket.name == "True"
            for link in store.outputs["Geometry"].links
        )
    assert "Back Smooth" not in inputs
    assert inputs["Rear Smooth"].default_value == 8
    assert inputs["Edge Turn"].default_value == pytest.approx(1.0)
    assert len(profile_powers) == 1


@pytest.mark.parametrize("boundary", ("split", "limit"))
def test_depth_cutout_bridge_closes_generated_boundaries(boundary):
    obj, set_value = surface(step=6, resolution=8)
    if boundary == "split":
        set_value("Depth Split", 0.5)
    else:
        set_value("Depth Limit", 2.0)
    front, front_faces = evaluated(obj)
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.2)
    points, faces = evaluated(obj)
    assert len(points) <= 2 * len(front)
    assert len(faces) == 2 * len(front_faces) + boundary_edge_count
    assert_closed(faces)
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
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.2)
    points, faces = evaluated(obj)
    assert len(points) == 2 * len(front)
    assert len(faces) == 2 * len(front_faces) + boundary_edge_count
    assert_closed(faces)
    _assert_oriented_closed(faces)


def test_depth_cutout_bridge_scales_beyond_4096_source_points():
    obj, set_value = surface(step=0, resolution=46)
    front, front_faces = evaluated(obj)
    assert len(front) > 4096
    boundary_edge_count = sum(len(neighbors) for neighbors in boundary_neighbors(front_faces).values()) // 2
    set_value("Thickness", 0.02)
    points, faces = evaluated(obj)
    assert len(points) == 2 * len(front)
    assert len(faces) == 2 * len(front_faces) + boundary_edge_count
    assert_closed(faces)
    _assert_oriented_closed(faces)


@pytest.mark.parametrize("mode", (0, 1))
@pytest.mark.parametrize("boundary_smooth", (0, 4, 16))
@pytest.mark.parametrize("rear_smooth", (0, 8))
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
    assert_closed(faces)
    _assert_oriented_closed(faces)
    _assert_positive_face_areas(points, faces)

    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        assert "UVMap" in mesh.uv_layers
        assert "o_balloon" in mesh.attributes
        assert "o_normal_reduction" in mesh.attributes
        assert not [item.name for item in mesh.attributes if item.name.startswith("_o_")]
    finally:
        result.to_mesh_clear()


def test_joined_single_smoothing_matches_identical_leaf_inputs():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    columns, rows = 12, 4
    points = [
        (
            x / columns,
            0.0,
            y / rows + (0.05 if y == rows and x % 2 else 0.0),
        )
        for y in range(rows + 1)
        for x in range(columns + 1)
    ]
    stride = columns + 1
    faces = []
    for y in range(rows):
        for x in range(columns):
            a = y * stride + x
            b = a + 1
            c = a + stride
            d = c + 1
            faces.extend(((a, b, d), (a, d, c)))
    reference = _object(points, [], faces, _smoothing_group("Independent Leaf Smooth", joined=False))
    candidate = _object(points, [], faces, _smoothing_group("Joined Leaf Smooth", joined=True))
    reference_front, reference_rear = _evaluated_leaf_points(reference)
    candidate_front, candidate_rear = _evaluated_leaf_points(candidate)

    np.testing.assert_allclose(reference_front, candidate_front, atol=1e-6)
    np.testing.assert_allclose(reference_rear, candidate_rear, atol=1e-6)
    top = np.arange(rows * stride, (rows + 1) * stride)

    def bends(values):
        line = values[top]
        return np.linalg.norm(line[2:] - 2 * line[1:-1] + line[:-2], axis=1).sum()

    assert bends(reference_rear) == pytest.approx(bends(candidate_rear), abs=1e-6)
