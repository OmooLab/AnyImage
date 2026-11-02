"""Evaluate panorama topology, validity, UVs and depth discontinuities."""

from collections import Counter

import bpy
import numpy as np
import pytest


from tests.support.panorama import panorama, evaluated


def free_edges(faces):
    edges = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, (*face[1:], face[0])))
    return sum(count == 1 for count in edges.values())


def test_panorama_object_normals_match_evaluated_mesh_coordinates():
    from tests.anyimage.server.support import load_server_module

    geometry = load_server_module("geometry.panorama")
    bases = geometry.camera_bases()
    rays = geometry.view_rays(64)
    camera_normals = -rays / np.linalg.norm(rays, axis=-1, keepdims=True)
    texture = geometry.merge_object_normals(
        [camera_normals] * len(bases), np.ones((12, 64, 64), bool), bases, 512, 256,
    )
    # Include the PNG quantization used by the job.
    texture = np.rint((texture + 1) * 127.5) / 127.5 - 1
    obj, _ = panorama(subdivide=3)
    evaluated_obj = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated_obj.to_mesh()
    try:
        uv = np.array([item.uv[:] for item in mesh.uv_layers["UVMap"].data])
        actual = geometry.sample_panorama(texture, geometry.uv_directions(uv[:, 0], 1 - uv[:, 1]))
        positions = np.array([mesh.vertices[loop.vertex_index].co[:] for loop in mesh.loops])
        expected = -positions / np.linalg.norm(positions, axis=-1, keepdims=True)
        np.testing.assert_allclose(actual, expected, atol=.012)
    finally:
        evaluated_obj.to_mesh_clear()


@pytest.mark.parametrize("subdivide", [0, 1, 4])
def test_quad_sphere_topology_and_radial_endpoints(subdivide):
    obj, set_value = panorama(subdivide=subdivide)
    dome = 200.0
    set_value("Dome Radius", dome)
    inputs = [s for s in obj.modifiers[0].node_group.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"]
    assert [s.name for s in inputs if s.socket_type == "NodeSocketImage"] == ["Depth Image"]
    assert next(s for s in inputs if s.name == "Subdivide").min_value == 0
    # Depth Scale blends between the dome sphere and the estimated distance.
    for scale, radius in ((0, dome), (0.5, dome + 0.5 * (3 - dome)), (1, 3)):
        set_value("Depth Scale", scale)
        points, faces, uv = evaluated(obj)
        assert len(faces) == 6 * 4 ** (subdivide + 1)
        assert all(len(face) == 4 for face in faces)
        np.testing.assert_allclose(np.linalg.norm(points, axis=1), radius, atol=1e-5)
        edges = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, (*face[1:], face[0])))
        assert set(edges.values()) == {2}
        assert len(points) - len(edges) + len(faces) == 2
        assert np.isfinite(uv).all()
        assert np.all((uv >= 0) & (uv <= 1))
        assert np.max(np.ptp(uv.reshape(-1, 4, 2)[..., 0], axis=1)) <= 0.5 + 1e-5


def test_depth_mask_keeps_only_the_faces_above_the_threshold():
    obj, set_value = panorama(alpha=0.5)
    assert not len(evaluated(obj)[0])
    set_value("Depth Mask", False)
    points, faces, _ = evaluated(obj)
    assert len(faces) == 384
    np.testing.assert_allclose(np.linalg.norm(points, axis=1), 500, atol=1e-5)
    set_value("Depth Mask", True)
    set_value("Mask Threshold", 0.49)
    assert len(evaluated(obj)[1]) == 384


def test_alpha_cut_keeps_the_ring_sharing_the_face_centre_contour():
    """Faces are judged at their centre, so the ring straddling the sky stays."""
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    obj, _ = panorama(3.0, alpha, subdivide=3)
    points, faces, _ = evaluated(obj)
    plain, _ = panorama(3.0, 1.0, subdivide=3)
    _, full, _ = evaluated(plain)
    # Judging faces by their corners would drop one more ring of the half sphere.
    assert len(faces) == len(full) // 2
    np.testing.assert_allclose(np.linalg.norm(points, axis=1), 3, atol=1e-5)


def test_invalid_depth_does_not_bleed_into_alpha_boundary():
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    depth = np.where(alpha, 3, 10000)
    obj, _ = panorama(depth, alpha, subdivide=4)
    points, _, _ = evaluated(obj)
    np.testing.assert_allclose(np.linalg.norm(points, axis=1), 3, atol=1e-5)


def test_linear_depth_reconstructs_flat_floor_without_sampling_rings():
    z = -np.cos((np.arange(64) + 0.5) * np.pi / 64)
    depth = np.broadcast_to((2 / np.maximum(-z, 0.1))[:, None], (64, 128))
    obj, _ = panorama(depth, subdivide=5)
    points, _, _ = evaluated(obj)
    rays = points / np.linalg.norm(points, axis=1, keepdims=True)
    floor = rays[:, 2] < -0.5
    error = points[floor, 2] + 2
    assert np.sqrt(np.mean(error ** 2)) < 0.002
    assert np.max(abs(error)) < 0.004


def test_masked_area_rests_on_the_dome_sphere():
    """Depth Mask keeps only the valid half; the excluded half rests on the dome."""
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    depth = np.where(alpha, 3.0, 1e-7)
    obj, set_value = panorama(depth, alpha, subdivide=3)
    points, faces, _ = evaluated(obj)
    # Depth Mask removes the masked half; the cut ring keeps its face depth.
    assert len(faces) == 768
    np.testing.assert_allclose(np.linalg.norm(points, axis=1), 3, atol=1e-3)
    set_value("Depth Mask", False)
    set_value("Dome Radius", 200.0)
    radii = np.linalg.norm(evaluated(obj)[0], axis=1)
    on_dome = np.isclose(radii, 200.0, atol=1e-3)
    assert on_dome.any() and np.isclose(radii, 3, atol=1e-3).any()
    assert np.all(on_dome | np.isclose(radii, 3, atol=1e-3))
    set_value("Dome Radius", 200.0)
    set_value("Depth Scale", 0)
    np.testing.assert_allclose(np.linalg.norm(evaluated(obj)[0], axis=1), 200, atol=1e-3)
    set_value("Depth Mask", True)
    assert len(evaluated(obj)[1]) == 768
    np.testing.assert_allclose(np.linalg.norm(evaluated(obj)[0], axis=1), 200, atol=1e-3)


def test_masked_region_ignores_its_own_depth_and_depth_scale():
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    depth = np.where(alpha, 3.0, 1e4)
    obj, set_value = panorama(depth, alpha, subdivide=3)
    set_value("Depth Mask", False)
    for scale in (0.0, 1.0):
        set_value("Depth Scale", scale)
        radii = np.linalg.norm(evaluated(obj)[0], axis=1)
        on_dome = np.isclose(radii, 500, atol=1e-3)
        assert on_dome.any()
        assert np.all(on_dome | np.isclose(radii, 3.0, atol=1e-3))


def test_masked_regions_keep_their_own_seam_edges():
    """Both regions reach the output, so the seam is a free edge on each side."""
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    plain, _ = panorama(3.0, 1.0, subdivide=3)
    whole, whole_faces, _ = evaluated(plain)
    obj, set_value = panorama(3.0, alpha, subdivide=3)
    set_value("Depth Mask", False)
    points, faces, _ = evaluated(obj)
    assert len(faces) == len(whole_faces)
    assert len(points) > len(whole)
    set_value("Depth Mask", True)
    assert free_edges(faces) == 2 * free_edges(evaluated(obj)[1])


@pytest.mark.parametrize("depth_scale,depth_mask", [(0.0, False), (0.5, False), (1.0, False), (1.0, True)])
def test_horizon_bend_follows_depth_displacement_and_smoothing(depth_scale, depth_mask):
    mask = np.ones((64, 128))
    mask[:, 64:] = 0
    depth = np.full((64, 128), 20.0)
    depth[:, 32:64] = 60.0
    obj, set_value = panorama(depth, mask, subdivide=3)
    set_value("Depth Scale", depth_scale)
    set_value("Depth Mask", depth_mask)
    set_value("Depth Split", 0.5)
    set_value("Boundary Smooth", 3)
    before, faces, uv = evaluated(obj)
    radii = np.linalg.norm(before, axis=1)
    for strength in (-1.0, 1.0):
        set_value("Horizon Bend", strength)
        after, after_faces, after_uv = evaluated(obj)
        expected = before.copy()
        expected[:, 2] += strength * np.sum(before[:, :2] ** 2, axis=1) / 1000
        expected *= (radii / np.linalg.norm(expected, axis=1))[:, None]
        np.testing.assert_allclose(after, expected, atol=5e-5)
        np.testing.assert_allclose(np.linalg.norm(after, axis=1), radii, atol=5e-5)
        assert faces == after_faces
        np.testing.assert_array_equal(uv, after_uv)
    set_value("Horizon Bend", 0)
    np.testing.assert_array_equal(evaluated(obj)[0], before)


def test_horizon_bend_lowers_distant_horizon_more_and_keeps_poles_fixed():
    depth = np.full((64, 128), 100.0)
    depth[:, 64:] = 200.0
    obj, set_value = panorama(depth, subdivide=3)
    before, _, _ = evaluated(obj)
    set_value("Horizon Bend", -1.0)
    after, _, _ = evaluated(obj)
    poles = np.linalg.norm(before[:, :2], axis=1) < 1e-6
    assert poles.sum() == 2
    np.testing.assert_allclose(after[poles], before[poles], atol=1e-6)
    horizon = abs(before[:, 2]) < 1e-6
    radii = np.linalg.norm(before, axis=1)
    near = horizon & np.isclose(radii, 100)
    far = horizon & np.isclose(radii, 200)
    assert near.any() and far.any()
    np.testing.assert_allclose(after[near, 2], -9.950372, atol=1e-5)
    np.testing.assert_allclose(after[far, 2], -39.223227, atol=1e-5)
    assert np.all(np.linalg.norm(after[horizon, :2], axis=1) < radii[horizon])


def test_horizon_bend_keeps_depth_surface_fixed_when_dome_radius_changes():
    mask = np.ones((64, 128))
    mask[:, 64:] = 0
    obj, set_value = panorama(60.0, mask, subdivide=3)
    set_value("Depth Mask", False)
    set_value("Boundary Smooth", 3)
    before, faces, uv = evaluated(obj)
    surface = np.linalg.norm(before, axis=1) < 100
    assert surface.any() and (~surface).any()
    set_value("Horizon Bend", -0.1)
    near, _, _ = evaluated(obj)
    set_value("Dome Radius", 1000.0)
    far, far_faces, far_uv = evaluated(obj)
    np.testing.assert_allclose(far[surface], near[surface], atol=1e-5)
    assert np.max(np.linalg.norm(far[~surface] - near[~surface], axis=1)) > 400
    assert far_faces == faces
    np.testing.assert_allclose(far_uv, uv, atol=1e-6)


def test_boundary_smooth_relaxes_both_masked_region_boundaries():
    """Boundary Smooth relaxes both regions at the seam and leaves their interiors."""
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    depth = np.where(alpha, 3.0, 1e4)
    depth[:, 56] = 30.0
    obj, set_value = panorama(depth, alpha, subdivide=3)
    set_value("Depth Mask", False)
    before, _, uv = evaluated(obj)
    assert np.all((uv >= 0) & (uv <= 1))
    low = np.isclose(np.linalg.norm(before, axis=1), 500, atol=1e-3)
    assert low.any()
    set_value("Boundary Smooth", 5)
    after, _, uv = evaluated(obj)
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    assert not any(attribute.name.startswith("_o_") for attribute in mesh.attributes)
    assert np.all((uv >= 0) & (uv <= 1))
    moved = np.linalg.norm(after - before, axis=1) > 1e-6
    assert moved[low].any() and moved[~low].any()
    assert not moved[low].all()
    np.testing.assert_allclose(np.linalg.norm(after[low & ~moved], axis=1), 500, atol=1e-5)


def test_flat_scale_without_mask_returns_a_whole_sphere():
    """Depth Scale 0 without the mask leaves the dome sphere uncut and unsplit."""
    alpha = np.ones((64, 128))
    alpha[:, 64:] = 0
    plain, _ = panorama(3.0, 1.0, subdivide=3)
    whole, whole_faces, _ = evaluated(plain)
    obj, set_value = panorama(np.where(alpha, 3.0, 1e4), alpha, subdivide=3)
    set_value("Depth Mask", False)
    set_value("Depth Scale", 0)
    points, faces, _ = evaluated(obj)
    assert len(faces) == len(whole_faces)
    assert len(points) == len(whole)
    assert free_edges(faces) == 0
    np.testing.assert_allclose(np.linalg.norm(points, axis=1), 500, atol=1e-6)


def test_controls_and_material_slot_inheritance():
    obj, set_value = panorama()
    group = obj.modifiers[0].node_group
    inputs = {s.name: s for s in group.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"}
    names = [item.name for item in group.interface.items_tree
             if item.item_type == "SOCKET" and item.in_out == "INPUT"]
    assert names[names.index("Subdivide"):names.index("Depth Scale") + 1] == [
        "Subdivide", "Dome Radius", "Horizon Bend", "Depth Scale",
    ]
    assert inputs["Dome Radius"].parent == inputs["Subdivide"].parent
    assert inputs["Dome Radius"].default_value == 500
    assert (inputs["Dome Radius"].min_value, inputs["Dome Radius"].max_value) == (1, 10000)
    assert inputs["Dome Radius"].subtype == "DISTANCE"
    assert inputs["Horizon Bend"].default_value == 0
    assert (inputs["Horizon Bend"].min_value, inputs["Horizon Bend"].max_value) == (-1, 1)
    assert inputs["Subdivide"].default_value == 6
    assert inputs["Horizon Bend"].subtype == "FACTOR"
    assert inputs["Mask Threshold"].parent.name == "Options"
    assert inputs["Boundary Smooth"].parent.name == "Options"
    assert "Smooth Weight" not in inputs
    assert inputs["Depth Mask"].parent == inputs["Subdivide"].parent
    assert inputs["Depth Mask"].default_value is True
    obj.data.from_pydata([(0, 0, 0)], [], [])
    material = bpy.data.materials.new("Slot Material")
    obj.data.materials.append(material)
    for name in ("First Slot", "Replacement Slot"):
        current = bpy.data.materials.new(name)
        obj.data.materials[0] = current
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = result.to_mesh()
        try:
            assert mesh.materials[0].original == current
            assert all(f.material_index == 0 and f.use_smooth for f in mesh.polygons)
        finally:
            result.to_mesh_clear()


def test_material_uv_matches_world_environment_and_faces_point_inward():
    obj, _ = panorama(subdivide=3)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        assert all(np.dot(face.normal, face.center) < 0 for face in mesh.polygons)
        for loop in mesh.loops:
            ray = np.array(mesh.vertices[loop.vertex_index].co)
            ray /= np.linalg.norm(ray)
            u, v = mesh.uv_layers.active.data[loop.index].uv
            if abs(ray[2]) < 0.999999:
                # Blender's zero-rotation equirectangular Environment Texture.
                expected_u = 0.5 - np.arctan2(ray[1], ray[0]) / (2 * np.pi)
                assert abs((u - expected_u + 0.5) % 1 - 0.5) < 1e-5
            assert abs(v - (1 - np.arccos(np.clip(ray[2], -1, 1)) / np.pi)) < 1e-5
    finally:
        result.to_mesh_clear()


def test_asymmetric_depth_matches_world_environment_directions():
    u, v = np.meshgrid((np.arange(128) + 0.5) / 128, (np.arange(64) + 0.5) / 64)
    longitude = np.pi - 2 * np.pi * u
    latitude = np.pi * (v - 0.5)
    depth = (3 + 0.4 * np.cos(latitude) * np.cos(longitude)
             + 0.2 * np.cos(latitude) * np.sin(longitude) + 0.1 * np.sin(latitude))
    obj, _ = panorama(depth, subdivide=3)
    points, _, _ = evaluated(obj)
    radii = np.linalg.norm(points, axis=1)
    rays = points / radii[:, None]
    expected = 3 + rays @ (0.4, 0.2, 0.1)
    # Pole samples clamp to the nearest pixel row, half a pixel from the pole.
    non_poles = abs(rays[:, 2]) < 0.999999
    np.testing.assert_allclose(radii[non_poles], expected[non_poles], atol=0.001)
    np.testing.assert_allclose(radii[~non_poles], expected[~non_poles], atol=0.011)


def test_depth_scale_gates_split_selection():
    depth = np.ones((64, 128))
    depth[:, 64:] = 7
    obj, set_value = panorama(depth)
    set_value("Depth Scale", 0)
    whole = evaluated(obj)
    set_value("Depth Split", 1)
    flat = evaluated(obj)
    # A flat projection keeps the sphere whole, whatever the split strength is.
    assert flat[1] == whole[1]
    np.testing.assert_allclose(flat[0], whole[0], atol=1e-6)
    set_value("Depth Scale", 1)
    assert len(evaluated(obj)[0]) > len(flat[0])


def test_split_strength_and_distance_scale_invariance():
    depth = np.ones((64, 128))
    depth[:, 64:] = 7
    signatures = []
    for scale in (0.01, 100):
        obj, set_value = panorama(depth * scale)
        counts = []
        for split in (0, 0.1, 0.5, 1):
            set_value("Depth Split", split)
            points, faces, uv = evaluated(obj)
            assert np.isfinite(points).all() and np.isfinite(uv).all()
            edges = Counter(tuple(sorted((a, b))) for f in faces for a, b in zip(f, (*f[1:], f[0])))
            counts.append(sum(n == 1 for n in edges.values()))
        assert counts[0] == 0 and counts[-1] > 0
        assert counts == sorted(counts)
        signatures.append(counts)
    assert signatures[0] == signatures[1]


def test_continuous_spherical_slope_does_not_split_at_seam_or_poles():
    u, v = np.meshgrid((np.arange(128) + 0.5) / 128, (np.arange(64) + 0.5) / 64)
    depth = 3 + 0.3 * np.cos(2 * np.pi * u) * np.sin(np.pi * v)
    obj, set_value = panorama(depth)
    original = evaluated(obj)
    set_value("Depth Split", 1)
    set_value("Boundary Smooth", 12)
    points, faces, uv = evaluated(obj)
    np.testing.assert_allclose(points, original[0], atol=1e-6)
    assert faces == original[1]
    np.testing.assert_allclose(uv, original[2])


def test_split_corners_keep_their_rays_and_own_face_distance():
    from scipy.spatial import cKDTree

    depth = np.ones((64, 128))
    depth[:, 64:] = 7
    obj, set_value = panorama(depth)
    original, _, _ = evaluated(obj)
    original_radii = np.linalg.norm(original, axis=1)
    original_rays = original / original_radii[:, None]
    set_value("Depth Split", 1)
    points, _, uv = evaluated(obj)
    radii = np.linalg.norm(points, axis=1)
    distance, indices = cKDTree(original_rays).query(points / radii[:, None])
    assert distance.max() < 1e-5
    counts = Counter(indices)
    uncut = np.array([counts[index] == 1 for index in indices])
    np.testing.assert_allclose(radii[uncut], original_radii[indices[uncut]], atol=1e-5)
    assert any(np.ptp(radii[indices == index]) > 4 for index, count in counts.items() if count > 1)
    assert np.max(np.ptp(uv.reshape(-1, 4, 2)[..., 0], axis=1)) <= 0.5 + 1e-5


@pytest.mark.parametrize("mask", [0.0, .25, .75, 1.0])
@pytest.mark.parametrize("depth_scale", [0.0, 1.0])
def test_panorama_emission_tracks_inverse_mask(mask, depth_scale):
    obj, set_value = panorama(alpha=mask)
    set_value("Depth Mask", False)
    set_value("Depth Scale", depth_scale)
    set_value("Horizon Bend", -0.1)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        attribute = mesh.attributes["o_emission"]
        assert attribute.domain == "CORNER" and attribute.data_type == "FLOAT"
        np.testing.assert_allclose([item.value for item in attribute.data], 1 - mask, atol=1e-6)
    finally:
        result.to_mesh_clear()


def test_panorama_emission_does_not_wrap_mask_at_poles():
    mask = np.broadcast_to(np.linspace(0, 1, 64)[:, None], (64, 128))
    obj, set_value = panorama(alpha=mask, subdivide=2)
    set_value("Depth Mask", False)
    set_value("Depth Scale", 0)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        v = np.array([item.uv.y for item in mesh.uv_layers["UVMap"].data])
        expected = 1 - np.clip((v * 64 - .5) / 63, 0, 1)
        actual = [item.value for item in mesh.attributes["o_emission"].data]
        np.testing.assert_allclose(actual, expected, atol=1e-6)
    finally:
        result.to_mesh_clear()
