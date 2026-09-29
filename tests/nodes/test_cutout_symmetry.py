"""Check the canonical Y mirror and final X orientation for Depth Symmetry."""

from collections import Counter

import bpy
import numpy as np
import pytest
from scipy.spatial import cKDTree

from anyimage.common.object import modifier_input_identifier, set_modifier_input
from tests.support.depth_surface import assert_closed
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


def _evaluated_uv(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return np.array([item.uv[:] for item in mesh.uv_layers["UVMap"].data])
    finally:
        result.to_mesh_clear()


def _open_edges(faces):
    counts = Counter(
        tuple(sorted((a, b))) for f in faces for a, b in zip(f, (*f[1:], f[0]))
    )
    return [edge for edge, count in counts.items() if count == 1]


def _marked_vertices(points, faces, marker, value):
    indices = {index for face, item in zip(faces, marker) if item == value for index in face}
    return points[sorted(indices)]


def _positions(points):
    return {tuple(np.round(point, 6)) for point in points}


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


def test_fill_closes_sides_and_keeps_the_seam_welded_when_disabled(symmetry):
    obj, _cutout, _mirror, _cutout_setter, mirror_setter = symmetry
    points, faces, marker = _evaluated(obj)
    tolerance = _tolerance(points)
    band = np.abs(points[:, 0]) <= tolerance

    assert_closed(faces)
    assert band.any()
    for face, value in zip(faces, marker):
        if value == 3:
            assert np.abs(points[list(face)][:, 0]).max() > tolerance

    mirror_setter("Fill Sides", False)
    points, faces, _marker = _evaluated(obj)
    tolerance = _tolerance(points)
    open_edges = _open_edges(faces)
    assert open_edges
    assert not any(
        np.abs(points[list(edge)][:, 0]).max() <= tolerance
        for edge in open_edges
    )


def test_fill_smooth_relaxes_the_junction_band(symmetry):
    obj, _cutout, _mirror, _cutout_setter, mirror_setter = symmetry
    for item in obj.data.uv_layers["UVMap"].data:
        item.uv.x += 0.1 * item.uv.y**2
    obj.data.update()
    mirror_setter("Fill Sides", True)
    mirror_setter("Smooth", 0)
    plain_points, plain_faces, plain_marker = _evaluated(obj)
    plain_uv = _evaluated_uv(obj)
    mirror_setter("Smooth", 4)
    smooth_points, smooth_faces, smooth_marker = _evaluated(obj)
    smooth_uv = _evaluated_uv(obj)
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
    assert np.isfinite(smooth_uv).all()
    assert cKDTree(smooth_points).query(smooth_points * (-1, 1, 1))[0].max() < 1e-5



def test_final_orientation_preserves_symmetry_and_normal_attributes(symmetry):
    obj, _cutout, _mirror, cutout_setter, _mirror_setter = symmetry
    cutout_setter("Mode", 1)
    cutout_setter("Thickness", 0.2, subtype="DISTANCE")
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()

    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated_obj.to_mesh()
    try:
        points = np.array([vertex.co[:] for vertex in mesh.vertices])
        assert len(points) and np.isfinite(points).all()
        assert cKDTree(points).query(points * (-1, 1, 1))[0].max() < 1e-5
        assert np.ptp(points[:, 2]) > 1.0
        assert all(face.use_smooth for face in mesh.polygons)
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
        uv = np.array([item.uv[:] for item in mesh.uv_layers["UVMap"].data])
        assert uv[:, 1].min() >= -1e-6 and uv[:, 1].max() <= 1.0 + 1e-6
        assert (uv[:, 1] < 0.5 - 1e-6).any()
        assert (uv[:, 1] > 0.5 + 1e-6).any()
    finally:
        evaluated_obj.to_mesh_clear()


def test_symmetry_preserves_source_uv_and_separates_regions(symmetry):
    obj, _cutout, _mirror, _cutout_setter, _mirror_setter = symmetry
    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated_obj.to_mesh()
    try:
        marker = np.array([item.value for item in mesh.attributes[FACE_ATTRIBUTE].data])
        owner_uv = {1: set(), 2: set()}
        for polygon, owner in zip(mesh.polygons, marker):
            values = np.array([
                mesh.uv_layers["UVMap"].data[index].uv.y
                for index in polygon.loop_indices
            ])
            assert values.min() >= -1e-6 and values.max() <= 1.0 + 1e-6
            if owner in owner_uv:
                owner_uv[int(owner)].update(
                    tuple(np.round(mesh.uv_layers["UVMap"].data[index].uv[:], 5))
                    for index in polygon.loop_indices
                )
        assert owner_uv[1] == owner_uv[2]
        regions = {item.value for item in mesh.attributes['o_image_region'].data}
        assert regions == {0, 2}
    finally:
        evaluated_obj.to_mesh_clear()
