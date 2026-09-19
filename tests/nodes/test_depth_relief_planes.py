"""Evaluate complete-image projection and rectangular surface topology."""

import bpy
import numpy as np
import pytest

from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from tests.support.planes import surface, relief, evaluated


@pytest.mark.parametrize("subdivide", [0, 3])
def test_zero_depth_matches_plane_geometry_and_uv(surface, subdivide):
    obj, set_value, plane, inputs, _ = surface
    set_value("Subdivide", subdivide)
    projected = evaluated(obj)
    modifier = obj.modifiers[0]
    modifier.node_group = plane
    for item in plane.interface.items_tree:
        if item.item_type == "SOCKET" and item.in_out == "INPUT":
            if item.name == "Subdivide":
                modifier[item.identifier] = subdivide
            elif item.name == "Thickness":
                modifier[item.identifier] = 0.0
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    regular = evaluated(obj)
    np.testing.assert_allclose(projected[0], regular[0], atol=1e-6)
    assert projected[1] == regular[1]
    np.testing.assert_allclose(projected[2], regular[2], atol=1e-6)
    assert projected[3:5] == regular[3:5]


@pytest.mark.parametrize("strength", [0, 2])
def test_camera_projection_and_reference_depth(surface, strength):
    obj, set_value, _, _, _ = surface
    base = evaluated(obj)
    uv = (base[0][:, [0, 2]] + (2, 1)) / (4, 2)
    texel = np.clip(uv * (16, 8), (0.5, 0.5), (15.5, 7.5))
    depth = 2 + texel[:, 0] / 16
    # Outline vertices keep the border ray and adopt the adjacent face-centre
    # depth, the same rule cut edges use to inherit their face sample.
    face_depth = np.zeros((len(base[0]), 2))
    for face in base[1]:
        center = np.mean(base[0][list(face)], axis=0)
        value = 2 + np.clip((center[0] + 2) / 4 * 16, 0.5, 15.5) / 16
        for index in face:
            face_depth[index] += (value, 1)
    face_depth = face_depth[:, 0] / face_depth[:, 1]
    on_outline = np.isclose(uv, 0).any(axis=1) | np.isclose(uv, 1).any(axis=1)
    ratio = np.where(on_outline, face_depth / depth, 1.0)
    camera = np.column_stack(((texel[:, 0] - 5) / 8 * ratio,
                              (depth * 0.5) * ratio - 1.2,
                              (texel[:, 1] - 3) / 8 * ratio))
    expected = base[0] * (1 - strength) + camera * strength
    set_value("Depth Scale", float(strength))
    projected = evaluated(obj)
    np.testing.assert_allclose(projected[0], expected, atol=1e-6)
    assert projected[1] == base[1]
    np.testing.assert_allclose(projected[2], base[2])
    set_value("Reference Depth", 1.7)
    shifted = evaluated(obj)[0]
    np.testing.assert_allclose(shifted - projected[0],
                               np.tile((0, -0.5 * strength, 0), (len(shifted), 1)), atol=1e-6)


@pytest.mark.parametrize("depth_scale", [0.0, 2.0])
def test_relief_depth_scale_sets_normal_reduction(relief, depth_scale):
    obj, set_value, *_ = relief
    set_value("Depth Scale", depth_scale)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        values = np.array([
            value.value for value in mesh.attributes[NORMAL_REDUCTION_ATTRIBUTE_NAME].data
        ])
    finally:
        result.to_mesh_clear()
    assert np.isfinite(values).all()
    if depth_scale == 0.0:
        np.testing.assert_allclose(values, 1.0)


@pytest.mark.parametrize("thickness", [0.2, 2.0])
def test_shell_keeps_front_and_closes_rectangular_boundary(surface, thickness):
    obj, set_value, _, _, _ = surface
    set_value("Depth Scale", 1.0)
    front = evaluated(obj)[0]
    set_value("Thickness", thickness)
    points, faces, uv, materials, indices, _ = evaluated(obj)
    front_set = {tuple(point) for point in front}
    assert front_set <= {tuple(point) for point in points}
    assert np.isfinite(points).all() and np.isfinite(uv).all()
    assert materials[0] == "Image" and set(indices) == {0}


@pytest.mark.parametrize("valid_only", [False, True])
def test_depth_split_preserves_faces_and_closes_each_shell(surface, valid_only):
    obj, set_value, _, _, image = surface
    pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(8, 16, 4)
    pixels[:, 8:, 2] += 10
    pixels[:2, :, 3] = 0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Scale", 1.0)
    set_value("Depth Mask", valid_only)
    base = evaluated(obj)
    set_value("Depth Split", 1.0)
    points, faces, uv, materials, indices, _ = evaluated(obj)
    assert len(points) > len(base[0])
    assert len(faces) == len(base[1])
    np.testing.assert_allclose(uv, base[2])
    assert (materials, indices) == base[3:5]
    set_value("Thickness", 0.2)
    shell_points, shell_faces, shell_uv, *_ = evaluated(obj)
    assert np.isfinite(shell_points).all() and np.isfinite(shell_uv).all()
    set_value("Thickness", 0.0)
    set_value("Depth Split", 0.0)
    restored = evaluated(obj)
    np.testing.assert_allclose(restored[0], base[0])
    assert restored[1] == base[1]


def test_depth_scale_gates_depth_split(surface):
    obj, set_value, _, _, image = surface
    pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(8, 16, 4)
    pixels[:, 8:, 2] += 10
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Scale", 1.0)
    whole = evaluated(obj)
    set_value("Depth Split", 1.0)
    split = evaluated(obj)
    assert len(split[0]) > len(whole[0])
    set_value("Depth Scale", 0.0)
    set_value("Depth Split", 0.0)
    flat = evaluated(obj)
    set_value("Depth Split", 1.0)
    cancelled = evaluated(obj)
    assert cancelled[1] == flat[1]
    np.testing.assert_allclose(cancelled[0], flat[0], atol=1e-6)


def test_depth_jump_keeps_rectangular_faces(surface):
    obj, set_value, _, _, image = surface
    base = evaluated(obj)
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[:, 8:, 2] = 10
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Scale", 1.0)
    result = evaluated(obj)
    assert result[1] == base[1]
    assert len(result[0]) == len(base[0])
    assert np.ptp(result[0][:, 1]) > 4


@pytest.mark.parametrize("thickness", [0.0, 0.4])
def test_relief_reads_z_and_keeps_the_base(relief, thickness):
    obj, set_value, _, inputs, image = relief
    set_value("Thickness", thickness)
    set_value("Depth Scale", 1.0)
    set_value("Reference Depth", 2.0)
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 0], pixels[..., 1], pixels[..., 2] = -9, 13, 2
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Uniform Scale", 0.5)
    first = evaluated(obj)
    assert np.isfinite(first[0]).all()
    assert np.ptp(first[0][:, 0]) > 0 and np.ptp(first[0][:, 2]) > 0
    pixels[..., 0], pixels[..., 1] = 31, -22
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Uniform Scale", 0.5)
    np.testing.assert_allclose(evaluated(obj)[0], first[0])
    assert obj.modifiers[0][inputs["Thickness"].identifier] == pytest.approx(thickness)


def test_zero_thickness_relief_keeps_far_depth_at_object_space_zero(relief):
    obj, set_value, _, _, _ = relief
    base = evaluated(obj)
    set_value("Reference Depth", 2.0)
    set_value("Depth Scale", 1.5)
    result = evaluated(obj)
    assert np.isfinite(result[0]).all()
    np.testing.assert_array_equal(result[0][:, [0, 2]], base[0][:, [0, 2]])
    assert result[1] == base[1]
    np.testing.assert_array_equal(result[2], base[2])


def test_relief_far_depth_stops_at_thickness_height(relief):
    obj, set_value, _, _, image = relief
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 2] = 2.0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Uniform Scale", 0.5)
    set_value("Reference Depth", 0.9)
    set_value("Depth Scale", 2.0)
    set_value("Thickness", 0.4)
    points = evaluated(obj)[0]
    assert np.isfinite(points).all()


def test_relief_offset_corrects_reference_before_direction_and_scale(relief):
    obj, set_value, _, _, image = relief
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 2] = 2.0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Uniform Scale", 0.5)
    set_value("Reference Depth", 1.0)
    set_value("Depth Direction", (0.2, 1.0, -0.1))
    set_value("Thickness", 0.0)
    set_value("Depth Scale", 1.5)
    set_value("Depth Offset", 1.0)
    raised = evaluated(obj)[0]
    set_value("Depth Offset", 0.5)
    lowered = evaluated(obj)[0]
    assert np.isfinite(raised).all() and np.isfinite(lowered).all()
    assert not np.allclose(raised[:, 1], lowered[:, 1], atol=1e-6)


def test_zero_depth_scale_keeps_relief_at_depth_zero(relief):
    obj, set_value, _, _, _ = relief
    set_value("Thickness", 0.4)
    set_value("Depth Offset", 1.0)
    set_value("Depth Scale", 0.0)
    points = evaluated(obj)[0]
    assert np.isfinite(points).all()


def test_negative_relief_offset_is_clamped_at_depth_zero(relief):
    obj, set_value, _, _, image = relief
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 2] = 1.0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Uniform Scale", 1.0)
    set_value("Reference Depth", 1.0)
    set_value("Depth Offset", -0.5)
    set_value("Depth Scale", 1.0)
    set_value("Thickness", 0.3)
    points = evaluated(obj)[0]
    assert np.isfinite(points).all()


def test_curved_shell_smooths_normals_without_shrinking_thickness(surface):
    obj, set_value, _, _, image = surface
    yy, xx = np.mgrid[:8, :16]
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 0] = (xx + 0.5 - 8) / 4
    pixels[..., 1] = (4 - yy - 0.5) / 4
    pixels[..., 2] = 2 + ((xx + 0.5 - 8) / 8) ** 2 + 0.12 * (xx % 2)
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Subdivide", 3)
    set_value("Depth Scale", 1.0)
    front, faces, *_ = evaluated(obj)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        raw_normals = np.array([v.normal[:] for v in mesh.vertices])
    finally:
        result.to_mesh_clear()
    thickness = 0.001
    set_value("Thickness", thickness)
    points = evaluated(obj)[0]
    distances = np.linalg.norm(points[:, None, :] - front[None, :, :], axis=2)
    source = distances.argmin(axis=1)
    distance = distances.min(axis=1)
    rear = distance > thickness * 0.5
    assert rear.sum() == len(front)
    assert len(set(source[rear])) == len(front)
    np.testing.assert_allclose(distance[rear], thickness, atol=1e-6)
    normals = np.empty_like(front)
    normals[source[rear]] = (front[source[rear]] - points[rear]) / thickness
    assert np.all(np.sum(normals * raw_normals, axis=1) > 0)
    edges = np.array(list({tuple(sorted((a, b))) for f in faces
                          for a, b in zip(f, (*f[1:], f[0]))}))
    roughness = lambda n: np.mean(np.linalg.norm(n[edges[:, 0]] - n[edges[:, 1]], axis=1))
    assert roughness(normals) < roughness(raw_normals)



def test_relief_direction_adjusts_depth_and_keeps_base(relief):
    thickness = 0.4
    direction = (0.2, 1, -0.1)
    obj, set_value, _, _, image = relief
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 2] = 2
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Thickness", thickness)
    set_value("Reference Depth", 2.0)
    layers = evaluated(obj)[0]
    weights = np.clip(layers[:, 1] / thickness, 0, 1) if thickness else np.ones(len(layers))
    set_value("Depth Scale", 0.5)
    base = evaluated(obj)
    set_value("Depth Direction", direction)
    result = evaluated(obj)
    front = base[0][:, 1] > 0
    expected = base[0].copy()
    if direction[1]:
        expected[front, 1] += 0.5 * weights[front] * (expected[front][:, [0, 2]] @ np.array([direction[0], direction[2]])) / direction[1]
    np.testing.assert_array_equal(result[0][:, [0, 2]], base[0][:, [0, 2]])
    assert np.isfinite(result[0]).all()
    assert result[1] == base[1]
    np.testing.assert_array_equal(result[2], base[2])


@pytest.mark.parametrize("pattern,threshold", [
    ("half", 0.9), ("stripe", 0.9),
])
def test_valid_only_keeps_faces_covering_valid_samples(surface, pattern, threshold):
    obj, set_value, _, inputs, _ = surface
    set_value("Mask Threshold", threshold)
    depth_image = obj.modifiers[0][inputs["Depth Image"].identifier]
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    alpha = np.ones(16, dtype=np.float32)
    if pattern == "invalid":
        alpha[:] = 0
    elif pattern == "partial":
        alpha[:] = 0.5
    elif pattern == "half":
        alpha[:8] = 0
    elif pattern == "stripe":
        alpha[:] = 0
        alpha[8] = 1
    pixels[..., 3] = alpha
    depth_image.pixels.foreach_set(pixels.ravel())
    depth_image.update()

    def sampled(x):
        return np.interp((x + 2) / 4 * 16 - 0.5, np.arange(16), alpha)

    for subdivisions in (0, 5):
        set_value("Subdivide", subdivisions)
        set_value("Depth Mask", False)
        base = evaluated(obj)
        expected = [face for face in base[1]
                    if sampled(np.mean(base[0][list(face)][:, 0])) >= threshold]
        set_value("Depth Mask", True)
        culled = evaluated(obj)
        assert len(culled[1]) == len(expected)
        expected_points = {tuple(base[0][index]) for face in expected for index in face}
        assert {tuple(point) for point in culled[0]} == expected_points
        assert np.isfinite(culled[2]).all()
        set_value("Depth Mask", False)
        np.testing.assert_allclose(evaluated(obj)[0], base[0])


def test_valid_only_precedes_closed_shell_generation(surface):
    obj, set_value, _, inputs, _ = surface
    depth_image = obj.modifiers[0][inputs["Depth Image"].identifier]
    pixels = np.asarray(depth_image.pixels[:], dtype=np.float32).reshape(8, 16, 4)
    pixels[:, :8, 3] = 0
    depth_image.pixels.foreach_set(pixels.ravel())
    depth_image.update()
    set_value("Depth Scale", 1.0)
    set_value("Thickness", 0.2)
    points, faces, uv, *_ = evaluated(obj)
    assert np.isfinite(points).all() and np.isfinite(uv).all()
