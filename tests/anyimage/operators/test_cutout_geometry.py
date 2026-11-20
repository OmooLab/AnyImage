import unittest
from types import SimpleNamespace
import numpy as np


from anyimage.operators.cutout_tool import geometry as cutout_geometry
from anyimage.operators.cutout_tool.contours import contour_area, extract_selection_contours, smooth_selection_contour


def mesh_component_count(faces):
    adjacency = {}
    for face in faces:
        for vertex in face:
            adjacency.setdefault(int(vertex), set())
        for start, end in zip(face, np.roll(face, -1)):
            adjacency[int(start)].add(int(end))
            adjacency[int(end)].add(int(start))
    remaining = set(adjacency)
    count = 0
    while remaining:
        count += 1
        pending = [remaining.pop()]
        while pending:
            vertex = pending.pop()
            connected = adjacency[vertex] & remaining
            remaining.difference_update(connected)
            pending.extend(connected)
    return count


def test_selection_contours_group_holes_with_their_connected_component():
    mask = np.zeros((120, 200), dtype=bool)
    mask[20:100, 50:160] = True
    mask[45:75, 80:120] = False
    mask[5:15, 5:15] = True

    components = extract_selection_contours(mask)
    assert sorted(len(component) for component in components) == [1, 2]
    contours = [contour for component in components for contour in component]
    bounds = [
        (*np.min(contour, axis=0), *np.max(contour, axis=0)) for contour in contours
    ]
    assert (50.0, 20.0, 160.0, 100.0) in bounds
    assert (80.0, 45.0, 120.0, 75.0) in bounds
    assert (5.0, 5.0, 15.0, 15.0) in bounds


def test_cutout_crop_bounds_map_to_the_source_plane():
    source = SimpleNamespace(
        data=SimpleNamespace(size=(200, 100)),
        empty_display_size=2.0,
        empty_image_offset=(-0.5, -0.5),
    )

    bounds = cutout_geometry.crop_plane_bounds(
        source,
        (50, 25, 150, 75),
        (200, 100),
    )

    np.testing.assert_allclose(bounds, (-0.5, 0.5, -0.25, 0.25))

def test_cutout_reference_mask_resamples_content_to_depth_resolution():
    content = np.zeros((4, 4), dtype=np.float32)
    content[:, 2:] = 1.0

    mask = cutout_geometry.build_reference_mask(content, (2, 2))

    assert mask.dtype == np.bool_
    np.testing.assert_array_equal(mask, ((False, True), (False, True)))


def test_cutout_domain_adapts_boundary_spacing_for_a_small_valid_selection():
    components = ((((2046, 2046), (2050, 2046), (2050, 2050), (2046, 2050)),),)

    domain = quality_domain(
        components, (4096, 4096),
        (-1.0, 1.0, -1.0, 1.0),
        0.5,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    assert len(domain[0]) >= 3
    assert len(domain[1]) >= 1


def test_cutout_domain_builds_a_full_image_at_minimum_detail():
    components = ((((0, 0), (4096, 0), (4096, 4096), (0, 4096)),),)

    domain = quality_domain(
        components, (4096, 4096),
        (-1.0, 1.0, -1.0, 1.0),
        0.5,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    assert len(domain[0]) >= 4
    assert len(domain[1]) >= 2


def test_cutout_domain_centers_vertices_on_crop_bounds():
    components = ((((0, 0), (100, 0), (100, 50), (0, 50)),),)

    vertices, _faces, uv, _profile = quality_domain(
        components, (100, 50),
        (2.0, 6.0, -3.0, 1.0),
        0.5,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    center = (vertices[:, :2].min(axis=0) + vertices[:, :2].max(axis=0)) * 0.5
    assert np.allclose(center, 0.0, atol=1e-6)
    expected_uv = vertices[:, [0, 2]] / np.asarray((4.0, 4.0)) + 0.5
    assert np.allclose(uv, expected_uv, atol=1e-6)


def test_cutout_domain_keeps_overlapping_selection_components_disconnected():
    components = (
        (
            ((20, 0), (100, 0), (100, 80), (20, 80)),
            ((50, 20), (50, 60), (70, 60), (70, 20)),
        ),
        (((0, 20), (40, 20), (40, 50), (0, 50)),),
    )
    domain = quality_domain(
        components, (120, 80),
        (0.0, 1.0, 0.0, 1.0),
        0.025,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    centers = domain[2][domain[1]].mean(axis=1)
    in_hole = (
        (centers[:, 0] > 0.45)
        & (centers[:, 0] < 0.55)
        & (centers[:, 1] > 0.35)
        & (centers[:, 1] < 0.65)
    )
    in_left_component = (
        (centers[:, 0] > 0.02)
        & (centers[:, 0] < 0.12)
        & (centers[:, 1] > 0.4)
        & (centers[:, 1] < 0.75)
    )

    assert not in_hole.any()
    assert in_left_component.any()
    assert mesh_component_count(domain[1]) == 2


class CutoutContourTest(unittest.TestCase):
    def test_cutout_contour_is_smooth_and_evenly_resampled(self):
        import numpy as np

        contour = smooth_selection_contour(
            ((0, 0), (3, 0), (4, 0), (4, 2), (0, 2)),
            0.25,
        )
        closed = np.vstack((contour, contour[0]))
        lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)

        self.assertGreater(len(contour), 20)
        self.assertGreater(contour_area(contour), 0.0)
        self.assertLess(float(lengths.std() / lengths.mean()), 0.15)


    def test_cutout_contour_smooths_pixel_stairs_before_coarse_resampling(self):
        import numpy as np

        staircase = [(0.0, 0.0)]
        for value in range(16):
            staircase.append((value + 1.0, float(value)))
            staircase.append((value + 1.0, value + 1.0))
        staircase.append((0.0, 16.0))
        smooth = smooth_selection_contour(staircase, 2.0)

        def diagonal_noise(points):
            points = np.asarray(points)
            selected = (
                (points[:, 0] > 2.0)
                & (points[:, 0] < 14.0)
                & (np.abs(points[:, 1] - points[:, 0]) < 2.0)
            )
            return float(np.std(points[selected, 1] - points[selected, 0]))

        self.assertLess(diagonal_noise(smooth), 0.05)


def quality_domain(components, image_size, bounds, spacing, metric):
    from anyimage.operators.cutout_tool import mesh
    ps, fs, cs = [], [], []
    offset = 0
    width, height = image_size
    pixel_scale = max((bounds[1]-bounds[0])/width, (bounds[3]-bounds[2])/height)
    for component in components:
        contours = [np.array(c, dtype=float) for c in component]
        p, f = mesh.triangulate(contours, spacing/pixel_scale)
        p, f = mesh.support_mesh(p, f)
        ps.append(p);fs.append(f+offset)
        cs.append((offset, offset+len(p), f, contours[0]));offset += len(p)
    p, f = np.concatenate(ps), np.concatenate(fs)
    boundary = mesh.boundary_vertices_from_faces(len(p), f)
    mask = np.zeros((height, width), dtype=bool)
    return cutout_geometry.cutout_domain((p, f, boundary, cs, mask), bounds, metric)
