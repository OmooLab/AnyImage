from types import SimpleNamespace

import bpy
import numpy as np
from mathutils import Matrix

from anyimage.operators.cutout_tool import geometry as cutout_geometry
from anyimage.operators.cutout_tool.contours import contour_area, extract_selection_contours, smooth_selection_contour


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


def test_small_selection_generates_a_centered_mesh_with_source_uvs():
    source = SimpleNamespace(
        data=SimpleNamespace(size=(4096, 4096)), matrix_world=Matrix.Identity(4),
        empty_display_size=2.0, empty_image_offset=(-0.5, -0.5),
    )
    crop = (2046, 2046, 2050, 2050)
    bounds = cutout_geometry.crop_plane_bounds(source, crop, source.data.size)
    shape = cutout_geometry.build_cutout_shape(bpy.context, source, .5, np.ones((4, 4)), bounds)
    assert len(shape.faces) > 0
    xz = shape.vertices[:, (0, 2)]
    np.testing.assert_allclose(xz.min(axis=0) + xz.max(axis=0), 0, atol=1e-6)
    np.testing.assert_allclose(shape.uv, xz / (2 * 4 / 4096) + .5, atol=1e-6)


def test_cutout_contour_is_smooth_and_evenly_resampled():
    contour = smooth_selection_contour(
        ((0, 0), (3, 0), (4, 0), (4, 2), (0, 2)),
        0.25,
    )
    closed = np.vstack((contour, contour[0]))
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)

    assert len(contour) > 20
    assert contour_area(contour) > 0
    assert lengths.std() / lengths.mean() < .15


def test_cutout_contour_smooths_pixel_stairs_before_coarse_resampling():
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

    assert diagonal_noise(smooth) < .05
