import numpy as np
import pytest
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from anyimage.operators.cutout_tool import geometry as g
from anyimage.operators.cutout_tool.balloon import poisson_balloon_profile
from anyimage.operators.cutout_tool import mesh


def boundary_distance(points, contours):
    starts = np.concatenate(contours)
    delta = np.concatenate([np.roll(c, -1, axis=0) - c for c in contours])
    offset = points[:, None] - starts
    fraction = np.clip(np.sum(offset * delta, axis=2) / np.sum(delta**2, axis=1), 0, 1)
    return np.linalg.norm(offset - fraction[..., None] * delta, axis=2).min(axis=1)


@pytest.mark.parametrize("fine_outline", [False, True])
@pytest.mark.parametrize("spacing", [2, 48])
def test_local_support_connects_coarse_and_dense_branches(fine_outline, spacing):
    result = mesh.build_mesh(branch_alpha(), spacing, 0.9, fine_outline=fine_outline)
    assert_supported(*result[:4])


def test_support_splits_shared_chords_and_preserves_boundary_and_area():
    points = np.array(((0., 0.), (20., 0.), (20., 2.), (0., 2.)))
    faces = np.array(((0, 1, 2), (0, 2, 3)))
    p, f = mesh.support_mesh(points, faces)
    assert len(p) == 5 and len(f) == 4
    assert_supported(p, f, g.boundary_vertices_from_faces(len(p), f), [None])
    triangles = p[f]
    assert np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]).sum() == pytest.approx(80)
    np.testing.assert_array_equal(p[:4], points)
    with pytest.raises(ValueError, match="limit"):
        mesh.support_mesh(points, faces, max_vertices=4)


def test_support_adds_one_sample_to_isolated_triangle_and_is_idempotent():
    points = np.array(((0., 0.), (20., 0.), (0., 2.)))
    faces = np.array(((0, 1, 2),))
    p, f = mesh.support_mesh(points, faces)
    assert len(p) == 4 and len(f) == 3
    assert_supported(p, f, g.boundary_vertices_from_faces(len(p), f), [None])
    again_p, again_f = mesh.support_mesh(p, f)
    np.testing.assert_array_equal(p, again_p)
    np.testing.assert_array_equal(f, again_f)


@pytest.mark.parametrize("spacing", [1, 16])
def test_pixel_corner_hole_contacts_produce_valid_supported_mesh(spacing):
    alpha = np.ones((40, 40))
    alpha[10:17, 10:17] = 0
    alpha[17:24, 17:24] = 0
    original = alpha.copy()
    result = mesh.build_mesh(alpha, spacing, .9)
    assert_supported(*result[:4])
    np.testing.assert_array_equal(alpha, original)
    p, f, b, _, _mask = result
    edges, counts = np.unique(np.sort(np.concatenate((f[:, :2], f[:, 1:], f[:, ::2])), axis=1), axis=0, return_counts=True)
    assert np.all(np.bincount(edges[counts == 1].ravel(), minlength=len(p))[b] == 2)
    centers = p[f].mean(axis=1)
    # The pixel-scale smoothing may round the hole corners; its interior stays open.
    assert not np.any((centers[:, 0] > 11) & (centers[:, 0] < 16) & (centers[:, 1] > 11) & (centers[:, 1] < 16))


def branch_alpha(offset=0):
    yy, xx = np.mgrid[:192, :192]
    xx = xx - offset
    yy = yy - offset
    alpha = (xx - 46) ** 2 + (yy - 48) ** 2 < 30**2
    path = np.asarray(((48, 48), (91, 70), (130, 110), (149, 167)))
    for a, b in zip(path[:-1], path[1:]):
        d = np.stack((xx - a[0], yy - a[1]), axis=-1)
        v = b - a
        t = np.clip(d @ v / (v @ v), 0, 1)
        alpha |= np.sum((d - t[..., None] * v) ** 2, axis=-1) < 2.5**2
    alpha |= (xx - 130) ** 2 + (yy - 110) ** 2 < 7**2
    return alpha.astype(float)


def assert_supported(points, faces, boundary, components):
    triangles = points[faces]
    area = np.abs(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    )
    assert np.isfinite(points).all() and np.all(area > 1e-8)
    edges = np.sort(np.concatenate((faces[:, :2], faces[:, 1:], faces[:, ::2])), axis=1)
    edges, counts = np.unique(edges, axis=0, return_counts=True)
    assert counts.max() <= 2
    interior = np.flatnonzero(~boundary)
    links = edges[~boundary[edges].any(axis=1)]
    graph = coo_matrix(
        (np.ones(len(links)), (links[:, 0], links[:, 1])),
        shape=(len(points), len(points)),
    ).tocsr()
    count, _labels = connected_components(graph[interior][:, interior], directed=False)
    assert count == len(components)
    assert not np.any(boundary[faces].all(axis=1))
    assert len(interior) >= len(components)
    profile = poisson_balloon_profile(points, faces, boundary)
    assert np.isfinite(profile).all()
    assert np.all(profile[interior] > 0)


@pytest.mark.parametrize("spacing", (4, 32))
@pytest.mark.parametrize("offset", (0, 1))
def test_fine_bent_leg_and_joint_have_connected_positive_support(spacing, offset):
    points, faces, boundary, components, _mask = mesh.build_mesh(
        branch_alpha(offset), spacing, 0.9
    )
    assert_supported(points, faces, boundary, components)
    interior = points[~boundary]
    checkpoints = np.array(((48, 48), (90, 70), (130, 110), (146, 159))) + offset
    distance, nearest = cKDTree(interior).query(checkpoints)
    assert distance.max() < 12
    edges = np.unique(
        np.sort(np.concatenate((faces[:, :2], faces[:, 1:], faces[:, ::2])), axis=1),
        axis=0,
    )
    links = edges[~boundary[edges].any(1)]
    graph = coo_matrix(
        (np.ones(len(links)), (links[:, 0], links[:, 1])),
        shape=(len(points), len(points)),
    ).tocsr()
    _, labels = connected_components(graph, directed=False)
    assert len(set(labels[np.flatnonzero(~boundary)[nearest]])) == 1


@pytest.mark.parametrize("spacing", (8, 32))
def test_fine_comb_hole_and_one_pixel_bridge(spacing):
    alpha = np.zeros((160, 180))
    alpha[15:145, 15:42] = 1
    alpha[45:115, 125:165] = 1
    alpha[75, 40:126] = 1
    alpha[65:90, 140:150] = 0
    for row in range(20, 140, 12):
        alpha[row : row + 2, 35:110] = 1
    result = mesh.build_mesh(alpha, spacing, 0.9)
    assert_supported(*result[:4])
    points, faces, _boundary, components, _mask = result
    assert len(components) == 1
    assert not np.any(
        g.points_inside_contours(
            points[faces].mean(axis=1),
            [np.asarray(((140, 65), (150, 65), (150, 90), (140, 90)))],
        )
    )


def test_fine_cleanup_uses_threshold_and_preserves_input_and_largest_island():
    alpha = np.zeros((40, 60))
    alpha[5:25, 5:25] = 0.5
    alpha[12, 20:45] = 0.5
    alpha[32:34, 50:52] = 1
    original = alpha.copy()
    filtered = mesh.filter_alpha(alpha, 0.3)
    assert filtered[12, 44] == 0.5 and filtered[32, 50] == 0
    np.testing.assert_array_equal(alpha, original)
    assert_supported(*mesh.build_mesh(alpha, 32, 0.3)[:4])
    assert_supported(*mesh.build_mesh(alpha, 32, 0.9)[:4])
    with pytest.raises(ValueError, match="no visible"):
        mesh.build_mesh(np.zeros((10, 10)), 32, 0.9)


def test_higher_detail_recovers_curve_instead_of_splitting_low_edges():
    yy, xx = np.mgrid[:240, :240]
    alpha = ((xx - 120) ** 2 + (yy - 120) ** 2 < 92**2).astype(float)
    reference = g.extract_selection_contours(alpha, max_resolution=240, threshold=0.9)
    source = g.resample_closed_contour(np.asarray(reference.components[0][0]), 0.5)
    errors = []
    for spacing in (32, 8, 4):
        contours = mesh.contours_for_component(reference.components[0], spacing)
        sampled = g.resample_closed_contour(contours[0], 0.5)
        forward = boundary_distance(source, contours)
        backward = boundary_distance(sampled, [np.asarray(reference.components[0][0])])
        errors.append(max(np.percentile(forward, 95), np.percentile(backward, 95)))
    assert errors[1] < errors[0]
    assert errors[2] <= errors[1] + 0.1


def test_fine_outline_softens_pixel_steps_in_normalized_coordinates():
    yy, xx = np.mgrid[:120, :120]
    alpha = ((xx - 60)**2 + (yy - 60)**2 < 45**2).astype(float)
    source = np.asarray(g.extract_selection_contours(alpha, max_resolution=120).components[0][0])
    transform = np.diag((8., 12.))
    contours = mesh.contours_for_component([source @ transform], 32, pixel_transform=transform)
    smoothed = contours[0] @ np.linalg.inv(transform)

    def turning(points):
        edges = np.roll(points, -1, axis=0) - points
        angles = np.arctan2(edges[:, 1], edges[:, 0])
        change = (np.roll(angles, -1) - angles + np.pi) % (2*np.pi) - np.pi
        return abs(change).sum()

    assert turning(smoothed) < turning(source) * .5
    assert boundary_distance(smoothed, [source]).max() < 1
    assert abs(g.contour_area(smoothed) / g.contour_area(source) - 1) < .02


@pytest.mark.parametrize("offset", [0, 4096, 16384])
def test_cdt_collinear_outline_samples_do_not_become_sliver_faces(offset):
    contour = np.asarray(((0.0, 0.0), (240.0, 0.0), (240.0, 160.0), (0.0, 160.0)))
    contour = contour @ np.asarray(((0.763, -0.646), (0.646, 0.763)))
    contour += np.asarray((420.123456, 540.234567)) + offset
    contours = [g.resample_closed_contour(contour, 16)]
    points, faces = mesh.triangulate(contours, 16)
    triangles = points[faces]
    area = abs(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    )
    longest_squared = np.max(
        np.sum((triangles - np.roll(triangles, 1, axis=1)) ** 2, axis=2), axis=1
    )
    assert np.min(area / longest_squared) > 1e-4
    assert area.sum() / 2 == pytest.approx(abs(g.contour_area(contour)), rel=1e-9)
    boundary = g.boundary_vertices_from_faces(len(points), faces)
    np.testing.assert_allclose(
        boundary_distance(points[boundary], [contour]), 0, atol=1e-9
    )
    # Every subdivided outline point survives; removing slivers must not skip it.
    assert cKDTree(points[boundary]).query(contours[0])[0].max() < 1e-9


def test_contour_validation_requires_separation_of_pixel_contacts():
    crossing = np.asarray(((0, 0), (4, 4), (0, 4), (4, 0)))
    assert not mesh.valid_contours([crossing])
    touching = np.asarray(
        ((0, 0), (2, 0), (2, 2), (4, 2), (4, 4), (2, 4), (2, 2), (0, 2))
    )
    assert not mesh.valid_contours([touching])
    assert mesh.valid_contours(mesh.separate_contour_contacts([touching.astype(float)]))


@pytest.mark.parametrize("fine_outline", [False, True])
def test_hole_policy_preserves_alpha_and_external_notches(fine_outline):
    alpha = np.ones((80, 80))
    alpha[10:12, 10:12] = 0
    alpha[20:29, 20:29] = 0
    alpha[40:41, 10:40] = 0
    alpha[:15, 60:65] = 0
    original = alpha.copy()
    mask = mesh.prepare_mask(alpha, 0.9, np.eye(2) * 3.2, fine_outline)
    assert mask[10, 10]
    assert mask[24, 24] == (not fine_outline)
    assert mask[40, 25] == (not fine_outline)
    assert not mask[0, 60]
    np.testing.assert_array_equal(alpha, original)


@pytest.mark.parametrize("size,filled", [(2, True), (3, False)])
def test_micro_hole_threshold_respects_world_transform(size, filled):
    alpha = np.ones((40, 40))
    alpha[10 : 10 + size, 10 : 10 + size] = 0
    mask = mesh.prepare_mask(alpha, 0.9, np.eye(2) * 3.2, True)
    assert bool(mask[10, 10]) == filled
    stretched = mesh.prepare_mask(alpha, 0.9, np.diag((6.4, 3.2)), True)
    assert not stretched[10, 10]


def test_filling_nested_hole_merges_island_without_overlap():
    alpha = np.zeros((80, 80))
    alpha[5:75, 5:75] = 1
    alpha[20:60, 20:60] = 0
    alpha[30:50, 30:50] = 1
    result = mesh.build_mesh(alpha, 8, 0.9, fine_outline=False)
    p, f, _, components, _mask = result
    assert len(components) == 1
    assert_supported(*result[:4])
    edges = np.unique(
        np.sort(np.concatenate((f[:, :2], f[:, 1:], f[:, ::2])), axis=1), axis=0
    )
    assert 1 - len(p) + len(edges) - len(f) == 0


