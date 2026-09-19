"""Check the canonical Y mirror and final X orientation for Depth Symmetry."""

from collections import Counter

import bpy
import numpy as np
import pytest
from scipy.spatial import cKDTree

from anyimage.common.object import modifier_input_identifier, set_modifier_input
from tests.support.depth_surface import assert_closed, evaluated
from nodes.common.normal_map import AXIS_ATTRIBUTE, FACE_ATTRIBUTE, ROTATION_ATTRIBUTE
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
        uv.data[loop.index].uv = ((column + 0.5) / count, (row + 0.5) / count)
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
    image.pixels.foreach_set(
        np.dstack((x, -z, depth, np.ones_like(x))).astype(np.float32).ravel()
    )

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


def test_symmetry_interface_and_cutout_defaults(symmetry):
    _obj, cutout, mirror, _cutout_setter, _mirror_setter = symmetry
    assert not any(node.bl_idname == "GeometryNodeMeshBoolean" for node in mirror.node_group.nodes)
    mirror_inputs = [
        item
        for item in mirror.node_group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    ]
    assert [item.name for item in mirror_inputs] == [
        "Geometry",
        "Direction",
        "Offset",
        "Scale",
        "Fill Sides",
        "Smooth",
        "Merge Distance",
    ]
    assert tuple(mirror_inputs[1].default_value) == (0, 0, 1)
    assert mirror_inputs[3].default_value == 1
    assert mirror_inputs[2].min_value == -10
    assert mirror_inputs[2].max_value == 10
    assert mirror_inputs[3].min_value == 0
    assert mirror_inputs[3].max_value == 2
    assert mirror_inputs[4].default_value is True
    assert mirror_inputs[5].default_value == 4
    assert mirror_inputs[6].default_value == pytest.approx(0.001)
    assert mirror_inputs[6].min_value == 0

    cutout_names = {
        item.name
        for item in cutout.node_group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    }
    assert "Depth Axis" not in cutout_names
    thickness = [
        item
        for item in cutout.node_group.interface.items_tree
        if item.item_type == "SOCKET" and item.name == "Thickness"
    ]
    assert len(thickness) == 2 and all(item.default_value == 0 for item in thickness)


def test_final_symmetry_axis_is_x_and_z_is_up(symmetry):
    obj, _cutout, _mirror, cutout_setter, _mirror_setter = symmetry
    cutout_setter("Mode", 1)
    cutout_setter("Thickness", 0.2, subtype="DISTANCE")
    points, faces = evaluated(obj)

    assert len(points) and np.isfinite(points).all()
    assert cKDTree(points).query(points * (-1, 1, 1))[0].max() < 1e-5
    assert np.ptp(points[:, 2]) > 1.0


def _tolerance(points):
    size = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
    return max(size, 1e-8) * 1e-7


def _evaluated(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        points = np.array([vertex.co[:] for vertex in mesh.vertices])
        faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
        marker = np.array([item.value for item in mesh.attributes[FACE_ATTRIBUTE].data])
    finally:
        result.to_mesh_clear()
    return points, faces, marker


def _open_edges(faces):
    counts = Counter(
        tuple(sorted((a, b))) for f in faces for a, b in zip(f, (*f[1:], f[0]))
    )
    return [edge for edge, count in counts.items() if count == 1]


def _marked_vertices(points, faces, marker, value):
    indices = {index for face, item in zip(faces, marker) if item == value for index in face}
    return points[sorted(indices)]


def _front_vertices(points, faces, marker, predicate):
    return np.array(
        [point for point in _marked_vertices(points, faces, marker, 1) if predicate(point)]
    )


def _positions(points):
    return {tuple(np.round(point, 6)) for point in points}


def _front_rim(points, faces, marker, tolerance):
    return _front_vertices(points, faces, marker, lambda point: abs(point[0]) <= tolerance)


def test_seam_clamps_geometry_onto_the_symmetry_plane(symmetry):
    obj, _cutout, _mirror, _cutout_setter, _mirror_setter = symmetry
    points, faces, marker = _evaluated(obj)
    tolerance = _tolerance(points)
    plane = np.abs(points[:, 0]) <= tolerance

    assert _marked_vertices(points, faces, marker, 1)[:, 0].min() >= -tolerance
    assert _marked_vertices(points, faces, marker, 2)[:, 0].max() <= tolerance
    assert plane.any()
    assert not any(all(plane[index] for index in face) for face in faces)
    # 跨界的面保留，切口环被回拉到对称面上。
    assert any(plane[list(face)].any() and not plane[list(face)].all() for face in faces)


def test_disabled_fill_keeps_the_welded_seam(symmetry):
    obj, _cutout, _mirror, _cutout_setter, mirror_setter = symmetry
    mirror_setter("Fill Sides", False)
    points, faces = evaluated(obj)
    tolerance = _tolerance(points)
    plane = np.abs(points[:, 0]) <= tolerance
    open_edges = _open_edges(faces)

    assert open_edges
    assert not any(plane[edge[0]] and plane[edge[1]] for edge in open_edges)


def test_merge_distance_snaps_the_welded_band(symmetry):
    """合并距离决定平面附近折平还是补面：带内直接焊住，带外的开口才补。"""
    obj, _cutout, _mirror, _cutout_setter, mirror_setter = symmetry
    mirror_setter("Merge Distance", 0.05, subtype="DISTANCE")
    points, faces, marker = _evaluated(obj)
    band = np.abs(points[:, 0]) < 0.05

    assert_closed(faces)
    assert band.any()
    # 补面墙体从带外开口挤向对称面，因此每张补面至少跨过半个合并距离。
    for face, value in zip(faces, marker):
        if value == 3:
            assert np.abs(points[list(face)][:, 0]).max() > 0.025

    mirror_setter("Fill Sides", False)
    points, faces, _marker = _evaluated(obj)
    band = np.abs(points[:, 0]) < 0.05

    # 合并距离之内的点全部折到对称面上，接缝直接焊住。
    assert np.abs(points[band][:, 0]).max() < _tolerance(points)
    assert not any(
        np.abs(points[list(edge)][:, 0]).max() < 0.05 for edge in _open_edges(faces)
    )


def test_fill_smooth_relaxes_the_junction_band(symmetry):
    obj, _cutout, _mirror, _cutout_setter, mirror_setter = symmetry
    mirror_setter("Fill Sides", True)
    mirror_setter("Smooth", 0)
    plain_points, plain_faces, plain_marker = _evaluated(obj)
    mirror_setter("Smooth", 4)
    smooth_points, smooth_faces, smooth_marker = _evaluated(obj)
    tolerance = _tolerance(plain_points)

    for points, faces in ((plain_points, plain_faces), (smooth_points, smooth_faces)):
        plane = np.abs(points[:, 0]) <= tolerance
        assert plane.any()
        assert not any(all(plane[index] for index in face) for face in faces)
        assert_closed(faces)
    # 焊好之后衔接带连同补面一起松弛，贴合对称面的一圈随之变形。
    band = 0.25 * np.ptp(plain_points[:, 0])
    plain_band = _positions(plain_points[np.abs(plain_points[:, 0]) <= band])
    smooth_band = _positions(smooth_points[np.abs(smooth_points[:, 0]) <= band])
    assert plain_band != smooth_band
    assert cKDTree(smooth_points).query(smooth_points * (-1, 1, 1))[0].max() < 1e-5


def test_object_normal_attributes_follow_final_orientation(symmetry):
    obj, _cutout, _mirror, cutout_setter, _mirror_setter = symmetry
    cutout_setter("Mode", 1)
    cutout_setter("Thickness", 0.2, subtype="DISTANCE")
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()

    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated_obj.to_mesh()
    try:
        assert AXIS_ATTRIBUTE in mesh.attributes
        assert ROTATION_ATTRIBUTE in mesh.attributes
        assert FACE_ATTRIBUTE in mesh.attributes
        axis = np.array([item.value for item in mesh.attributes[AXIS_ATTRIBUTE].data])
        face = np.array([item.value for item in mesh.attributes[FACE_ATTRIBUTE].data])
        rotation = np.array(
            [item.vector[:] for item in mesh.attributes[ROTATION_ATTRIBUTE].data]
        )
        assert np.allclose(axis, 1)
        assert set(np.unique(face)) <= {1, 2, 3}
        assert np.isfinite(rotation).all()
    finally:
        evaluated_obj.to_mesh_clear()
