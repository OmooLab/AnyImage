import builtins
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np


from anyimage.common.selection import SelectionPath, rasterize_selection_path
from anyimage.operators.cutout_tool import geometry as cutout_geometry
from anyimage.operators.cutout_tool import object as cutout_object
from anyimage.operators.cutout_tool import shape as cutout_shape
from anyimage.operators.cutout_tool.geometry import SelectionContours, extract_selection_contours


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


def test_cutout_node_groups_are_loaded_from_the_asset():
    loaded = object()
    with patch.object(
        cutout_object, "load_node_group", return_value=loaded
    ) as load:
        for shape in cutout_shape.CUTOUT_NODE_GROUP_NAMES:
            assert cutout_object.load_cutout_node_group(shape) is loaded
            load.assert_called_with(cutout_shape.CUTOUT_NODE_GROUP_NAMES[shape])
        assert load.call_count == 4


def test_selection_contours_group_holes_with_their_connected_component():
    alpha = np.zeros((120, 200), dtype=np.uint8)
    alpha[20:100, 50:160] = 255
    alpha[45:75, 80:120] = 0
    alpha[5:15, 5:15] = 255

    selection_contours = extract_selection_contours(
        alpha,
        max_resolution=200,
    )

    assert selection_contours.image_size == (200, 120)
    assert sorted(len(component) for component in selection_contours.components) == [1, 2]
    contours = [
        contour for component in selection_contours.components for contour in component
    ]
    bounds = [
        (*np.min(contour, axis=0), *np.max(contour, axis=0)) for contour in contours
    ]
    assert (50.0, 20.0, 160.0, 100.0) in bounds
    assert (80.0, 45.0, 120.0, 75.0) in bounds
    assert (5.0, 5.0, 15.0, 15.0) in bounds


def test_selection_contours_accept_blender_float_mask_with_a_hole():
    alpha = np.zeros((120, 200), dtype=np.float32)
    alpha[20:100, 50:160] = 1.0
    alpha[45:75, 80:120] = 0.0

    selection_contours = extract_selection_contours(
        alpha,
        max_resolution=200,
    )

    assert selection_contours.image_size == (200, 120)
    assert len(selection_contours.components) == 1
    assert len(selection_contours.components[0]) == 2


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


def test_blender_cutout_alpha_pipeline_does_not_import_pillow():
    original_import = builtins.__import__

    def without_pillow(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ModuleNotFoundError("Pillow is unavailable in Blender")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=without_pillow):
        selection_mask = rasterize_selection_path(
            (48, 32),
            SelectionPath(points=((6, 4), (42, 4), (42, 28), (6, 28))),
            antialias=True,
        )
        antialiased = selection_mask.full_values((48, 32))
        selection_contours = extract_selection_contours(
            antialiased,
            max_resolution=24,
        )

    assert selection_contours.image_size == (48, 32)
    assert selection_contours.components
    assert np.any((antialiased > 0.0) & (antialiased < 1.0))

def test_cutout_domain_adapts_boundary_spacing_for_a_small_valid_selection():
    components = ((((2046, 2046), (2050, 2046), (2050, 2050), (2046, 2050)),),)

    domain = quality_domain(
        SelectionContours(components, (4096, 4096)),
        (-1.0, 1.0, -1.0, 1.0),
        0.5,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    assert len(domain[0]) >= 3
    assert len(domain[1]) >= 1


def test_cutout_domain_builds_a_full_image_at_minimum_detail():
    components = ((((0, 0), (4096, 0), (4096, 4096), (0, 4096)),),)

    domain = quality_domain(
        SelectionContours(components, (4096, 4096)),
        (-1.0, 1.0, -1.0, 1.0),
        0.5,
        ((1.0, 0.0), (0.0, 1.0)),
    )

    assert len(domain[0]) >= 4
    assert len(domain[1]) >= 2


def test_cutout_domain_centers_vertices_on_crop_bounds():
    components = ((((0, 0), (100, 0), (100, 50), (0, 50)),),)

    vertices, _faces, uv, _boundary, _planar, _profile = quality_domain(
        SelectionContours(components, (100, 50)),
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
        SelectionContours(components, (120, 80)),
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

        contour = cutout_geometry.smooth_selection_contour(
            ((0, 0), (3, 0), (4, 0), (4, 2), (0, 2)),
            0.25,
        )
        closed = np.vstack((contour, contour[0]))
        lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)

        self.assertGreater(len(contour), 20)
        self.assertGreater(cutout_geometry.contour_area(contour), 0.0)
        self.assertLess(float(lengths.std() / lengths.mean()), 0.15)


    def test_cutout_contour_smooths_pixel_stairs_before_coarse_resampling(self):
        import numpy as np

        staircase = [(0.0, 0.0)]
        for value in range(16):
            staircase.append((value + 1.0, float(value)))
            staircase.append((value + 1.0, value + 1.0))
        staircase.append((0.0, 16.0))
        smooth = cutout_geometry.smooth_selection_contour(staircase, 2.0)

        def diagonal_noise(points):
            points = np.asarray(points)
            selected = (
                (points[:, 0] > 2.0)
                & (points[:, 0] < 14.0)
                & (np.abs(points[:, 1] - points[:, 0]) < 2.0)
            )
            return float(np.std(points[selected, 1] - points[selected, 0]))

        self.assertLess(diagonal_noise(smooth), 0.05)


def quality_domain(selection, bounds, spacing, metric):
    from anyimage.operators.cutout_tool import mesh
    ps, fs, cs = [], [], []
    offset = 0
    width, height = selection.image_size
    pixel_scale = max((bounds[1]-bounds[0])/width, (bounds[3]-bounds[2])/height)
    for component in selection.components:
        contours = [np.array(c, dtype=float) for c in component]
        p, f = mesh.triangulate(contours, spacing/pixel_scale)
        p, f = mesh.support_mesh(p, f)
        ps.append(p);fs.append(f+offset)
        cs.append((offset, offset+len(p), f, contours[0]));offset += len(p)
    p, f = np.concatenate(ps), np.concatenate(fs)
    return cutout_geometry.cutout_domain((p, f, cutout_geometry.boundary_vertices_from_faces(len(p), f), cs, selection.image_size), bounds, metric)
