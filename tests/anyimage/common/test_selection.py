import json
import numpy as np
import pytest


from anyimage.common import selection


def reference_selection_mask(
    image_size,
    selection_path,
    *,
    antialias=False,
):
    width, height = map(int, image_size)
    points = np.asarray(selection_path.points, dtype=np.float64)
    x = np.arange(width, dtype=np.float64) + 0.5
    y = np.arange(height, dtype=np.float64) + 0.5
    winding = np.zeros((height, width), dtype=np.int16)
    previous = points[-1]
    for current in points:
        crosses = (current[1] > y) != (previous[1] > y)
        edge_x = (previous[0] - current[0]) * (y - current[1]) / (
            previous[1] - current[1] + 1e-300
        ) + current[0]
        selected = crosses[:, None] & (x[None, :] < edge_x[:, None])
        winding += selected * (1 if current[1] > previous[1] else -1)
        previous = current
    mask = winding != 0
    mask = (
        selection._antialias_mask(mask)
        if antialias
        else mask.astype(np.float32)
    )
    bounds = selection._selection_canvas_bounds(
        image_size,
        selection_path,
        2 if antialias else 0,
    )
    left, top, right, bottom = bounds
    mask = mask[top:bottom, left:right]
    if not np.any(mask > 0.0):
        raise selection.ImageEditWarning(
            "The selection contains no visible image pixels"
        )
    return selection.SelectionMask(mask, bounds)


def assert_matches_reference(image_size, selection_path, **options):
    try:
        expected = reference_selection_mask(image_size, selection_path, **options)
    except selection.ImageEditWarning:
        with pytest.raises(selection.ImageEditWarning):
            selection.rasterize_selection_path(
                image_size,
                selection_path,
                **options,
            )
        return
    actual = selection.rasterize_selection_path(
        image_size,
        selection_path,
        **options,
    )
    assert actual.bounds == expected.bounds
    np.testing.assert_array_equal(actual.values, expected.values)


def test_selection_path_json_contains_only_points():
    selection_path = selection.SelectionPath(
        points=((1, 2), (8, 2), (4, 9)),
    )
    value = selection_path.to_json()

    assert set(json.loads(value)) == {"points"}
    assert selection.SelectionPath.from_json(value) == selection_path
    with pytest.raises(ValueError, match="Selection Path data is invalid"):
        selection.SelectionPath.from_json(
            json.dumps(
                {
                    "points": selection_path.points,
                    "fill_rule": "NONZERO",
                }
            )
        )


def test_nonzero_winding_keeps_same_direction_overlap():
    points = (
        (1, 1),
        (7, 1),
        (7, 7),
        (1, 7),
        (1, 1),
        (4, 1),
        (10, 1),
        (10, 7),
        (4, 7),
        (4, 1),
        (1, 1),
    )

    mask = selection.rasterize_selection_path(
        (12, 9),
        selection.SelectionPath(points),
    ).full_values((12, 9))

    assert mask[3, 5] == 1.0


def test_scanline_matches_reference_for_edge_cases():
    paths = (
        ((1, 1), (15, 1), (15, 10), (1, 10)),
        ((0.2, 0.3), (15.8, 2.1), (8.4, 11.7)),
        ((1, 1), (15, 1), (15, 5), (7, 5), (7, 11), (1, 11)),
        ((1, 1), (15, 11), (1, 11), (15, 1)),
        ((-8, -3), (10, 1), (23, 8), (7, 18), (-4, 10)),
    )
    for points in paths:
        for antialias in (False, True):
            assert_matches_reference(
                (18, 14),
                selection.SelectionPath(points),
                antialias=antialias,
            )


def test_scanline_matches_reference_for_random_paths():
    random = np.random.default_rng(20260901)
    for _index in range(40):
        point_count = int(random.integers(3, 60))
        points = tuple(
            map(
                tuple,
                random.uniform((-8, -6), (40, 30), size=(point_count, 2)),
            )
        )
        for antialias in (False, True):
            assert_matches_reference(
                (32, 24),
                selection.SelectionPath(points),
                antialias=antialias,
            )


def test_antialias_uses_only_padded_local_canvas(monkeypatch):
    selection_path = selection.SelectionPath(
        ((100, 200), (500, 200), (500, 600), (100, 600))
    )
    calls = []
    rasterize = selection._rasterize_path

    def record(bounds, points):
        calls.append(bounds)
        return rasterize(bounds, points)

    monkeypatch.setattr(selection, "_rasterize_path", record)

    selection.rasterize_selection_path(
        (5120, 2880),
        selection_path,
        antialias=True,
    )

    assert calls == [(98, 198, 502, 602)]


def test_high_resolution_lasso_allocates_one_local_scanline_table(monkeypatch):
    angles = np.arange(1000, dtype=np.float64) * (2.0 * np.pi / 1000.0)
    points = tuple(
        zip(
            2560.0 + 500.0 * np.cos(angles),
            1440.0 + 300.0 * np.sin(angles),
        )
    )
    bounds = selection.selection_path_bounds(points)
    allocations = []
    zeros = np.zeros

    def record(shape, *args, **kwargs):
        allocations.append(shape)
        return zeros(shape, *args, **kwargs)

    monkeypatch.setattr(np, "zeros", record)

    mask = selection._rasterize_path(bounds, points)

    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    assert mask.shape == (height, width)
    assert allocations == [(height, width + 1)]
    assert (height, width) != (2880, 5120)
