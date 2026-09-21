"""Verify shared Depth calibration and metadata from Depth artifacts."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from anyimage.common.coordinate import canonical_direction_to_symmetry_legacy
from anyimage.common.depth import (
    FLAT_DEPTH_DIRECTION,
    REFERENCE_DEPTH_BASELINE,
    depth_uniform_scale,
    fit_depth_direction,
    fit_symmetry_depth_direction,
    load_depth_metadata,
    median_depth,
    reference_depth,
)
from tests.support.image_objects import _depth_image


def _camera_depth_image(depth, alpha=None):
    depth = np.asarray(depth, dtype=np.float32)
    points = np.zeros((*depth.shape, 3), dtype=np.float32)
    points[..., 2] = depth
    if alpha is None:
        alpha = np.ones(depth.shape, dtype=np.float32)
    return _depth_image(points, alpha)


def test_depth_metadata_loader_reads_only_size_and_intrinsics(tmp_path):
    path = tmp_path / "depth.json"
    path.write_text(
        json.dumps(
            {
                "image_size": [3, 2],
                "intrinsics": np.eye(3).tolist(),
            }
        ),
        encoding="utf-8",
    )

    metadata = load_depth_metadata(path)

    assert metadata == {
        "image_size": (3, 2),
        "intrinsics": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    }


def test_base_plane_fit_is_stable_for_a_slender_diagonal_domain():
    along = np.linspace(-1.0, 1.0, 101)
    across = np.resize(np.asarray((-0.01, 0.0, 0.01)), len(along))
    coordinates = np.column_stack((along - across, along + across))
    values = 0.4 * along + np.sign(across) * 0.05

    direction = fit_depth_direction(
        coordinates,
        values + 2.0,
        np.ones(len(values), dtype=bool),
        1.0,
    )
    slopes = np.asarray(direction[:2]) / direction[2]
    selected_plane = coordinates @ slopes
    corners = np.asarray(((-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)))
    corner_plane = corners @ slopes

    assert np.ptp(corner_plane) <= np.ptp(selected_plane) * 1.25
    assert np.corrcoef(selected_plane, along)[0, 1] > 0.99


def test_reference_depth_uses_the_upper_depth_percentile():
    depth = np.linspace(1.0, 1.2, 400, dtype=np.float32).reshape(20, 20)

    reference = reference_depth(_camera_depth_image(depth))

    assert reference == pytest.approx(float(np.percentile(depth, 95.0)))
    assert reference > float(np.median(depth))


def test_reference_depth_ignores_transparent_invalid_and_non_positive_pixels():
    depth = np.asarray(
        ((1.0, 1.05, 1.1, 9.0), (1.15, 0.0, np.nan, 1.2)),
        dtype=np.float32,
    )
    alpha = np.asarray(
        ((True, True, True, False), (True, True, True, True)),
    )

    reference = reference_depth(_camera_depth_image(depth, alpha))

    assert reference == pytest.approx(
        float(np.percentile(np.asarray((1.0, 1.05, 1.1, 1.15, 1.2)), 95.0))
    )


def test_reference_depth_narrows_its_domain_to_the_mask():
    depth = np.asarray(((1.0, 1.05, 1.1, 1.15),), dtype=np.float32)
    image = _camera_depth_image(depth)
    mask = np.asarray(((False, False, True, True),))

    assert reference_depth(image) == pytest.approx(
        float(np.percentile(depth, 95.0))
    )
    assert reference_depth(image, mask) == pytest.approx(
        float(np.percentile(np.asarray((1.1, 1.15)), 95.0))
    )


def test_reference_depth_ignores_soft_depth_alpha():
    depth = np.asarray(((1.0, 1.05, 1.1, 1.15),), dtype=np.float32)
    image = _camera_depth_image(depth, ((1.0, 1.0, 0.9, 0.6),))

    assert reference_depth(image) == pytest.approx(
        float(np.percentile(np.asarray((1.0, 1.05)), 95.0))
    )


def test_reference_depth_ignores_a_distant_tail():
    depth = np.asarray(((2.0, 4.0, 6.0, 1000.0),), dtype=np.float32)

    reference = reference_depth(_camera_depth_image(depth))

    assert reference == pytest.approx(
        float(np.percentile(np.asarray((2.0, 4.0)), 95.0))
    )


def test_reference_depth_follows_the_content_scale_when_everything_is_far():
    depth = np.asarray(((9.4, 10.6, 11.6, 13.0),), dtype=np.float32)

    reference = reference_depth(_camera_depth_image(depth))

    assert reference == pytest.approx(
        float(np.percentile(np.asarray((9.4, 10.6, 11.6)), 95.0))
    )


def test_reference_depth_falls_back_to_the_baseline_without_a_selection():
    transparent = _camera_depth_image(
        np.zeros((2, 2), dtype=np.float32),
        np.zeros((2, 2), dtype=np.float32),
    )

    assert reference_depth(transparent) == pytest.approx(REFERENCE_DEPTH_BASELINE)


def test_median_depth_uses_the_reference_validity_and_selection_domain():
    depth = np.asarray(((1.0, 3.0, 5.0, np.nan),), dtype=np.float32)
    alpha = np.asarray(((1.0, 1.0, 1.0, 1.0),), dtype=np.float32)
    image = _camera_depth_image(depth, alpha)

    assert median_depth(image) == pytest.approx(3.0)
    assert median_depth(image, ((False, True, True, True),)) == pytest.approx(4.0)


def test_median_depth_falls_back_without_usable_selected_depth():
    image = _camera_depth_image(((2.0, 4.0),), ((1.0, 0.0),))

    assert median_depth(image, ((False, True),)) == pytest.approx(
        REFERENCE_DEPTH_BASELINE
    )


def test_symmetry_depth_direction_fits_a_sloped_base_plane():
    vertices = []
    uv = []
    camera_depth = np.empty((3, 3), dtype=np.float32)
    for row in range(3):
        for column in range(3):
            local_x, local_y = column - 1.0, 1.0 - row
            vertices.append((local_x, 0.0, local_y))
            uv.append((column * 0.5, 1.0 - row * 0.5))
            camera_depth[row, column] = 2.0 + 0.2 * local_x + 0.1 * local_y

    direction = fit_symmetry_depth_direction(
        _camera_depth_image(camera_depth),
        vertices,
        uv,
        0.5,
    )

    expected = np.asarray((0.1, 1.0, 0.05), dtype=np.float64)
    expected /= np.linalg.norm(expected)
    assert np.allclose(direction, expected, atol=1e-6)


def test_symmetry_depth_direction_returns_the_flat_direction_without_samples():
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    uv = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
    depth = np.ones((2, 2), dtype=np.float32)
    image = _camera_depth_image(depth, np.zeros((2, 2), dtype=bool))

    direction = fit_symmetry_depth_direction(image, vertices, uv, 1.0)

    assert direction == FLAT_DEPTH_DIRECTION
    assert canonical_direction_to_symmetry_legacy(direction) == (0.0, 0.0, 1.0)


def test_depth_uniform_scale_converts_model_units_at_the_reference_depth():
    metadata = {
        "intrinsics": ((100.0, 0.0, 50.0), (0.0, 100.0, 25.0), (0.0, 0.0, 1.0)),
        "image_size": (101, 51),
    }

    uniform_scale = depth_uniform_scale(
        SimpleNamespace(),
        metadata,
        2.0,
        bounds=(-2.0, 2.0, -1.0, 1.0),
    )

    assert uniform_scale == pytest.approx(2.0)
