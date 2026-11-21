from anyimage.common import polygon as polygon_geometry
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np


from anyimage.common import image_gesture
from anyimage.operators import mask_tool as mask


def test_simplified_segments_bound_every_original_sample():
    raw = [(float(x), float(20 * np.sin(x / 15))) for x in np.arange(0, 160, 0.2)]
    path, samples = [], []
    for point in raw:
        image_gesture.append_lasso_point(path, point, samples)
    assert len(path) < len(raw) / 5
    for start, end in zip(path, path[1:]):
        segment = np.array(end) - start
        points = np.array([point for point in raw if start[0] <= point[0] <= end[0]])
        factor = np.clip((points - start) @ segment / (segment @ segment), 0, 1)
        distances = np.linalg.norm(points - (np.array(start) + factor[:, None] * segment), axis=1)
        assert distances.max() <= 0.75 + 1e-10


def test_straight_stroke_is_independent_of_segmentation():
    size = (160, 160)
    sparse = ((40, 70), (110, 70))
    dense = tuple((x, 70) for x in range(40, 111, 5))
    first, second = [mask.rasterize_brush_path(size, path, 5, lambda p: p)
                     for path in (sparse, dense)]
    assert first.bounds == second.bounds
    np.testing.assert_array_equal(first.values, second.values)


def test_incremental_preview_matches_full_union_when_tail_moves_and_crosses():
    cache = mask.BrushPreview()
    path = [(10, 10)]
    operations = [(False, (100, 100)), (True, (110, 90)), (False, (10, 90)),
                  (False, (110, 10)), (True, (105, 15)), (False, (10, 10))]
    for replace, point in [(False, None), *operations]:
        if point is not None:
            if replace:
                path[-1] = point
            else:
                path.append(point)
        cache.update(path, 8)
        reference = {round(bottom / cache.step): intervals
                     for bottom, _, intervals in polygon_geometry.scanline_union_bands(
                         polygon_geometry.brush_footprint_polygons(path, 8), cache.step)
                     if intervals}
        assert cache.coverage.keys() == reference.keys()
        for row in reference:
            np.testing.assert_allclose(cache.coverage[row], reference[row], atol=1e-10)


def test_preview_reuses_batches_and_limits_updates_to_changed_rows():
    cache = mask.BrushPreview()
    path = [(10, y) for y in range(0, 800, 10)]
    cache.update(path, 5)
    gpu = SimpleNamespace(shader=Mock(), state=Mock())
    build = Mock(side_effect=lambda *args: Mock())
    with patch.dict(sys.modules, {"gpu": gpu, "gpu_extras.batch": SimpleNamespace(batch_for_shader=build)}):
        cache.draw((1, 1, 1, 0.16))
        initial = dict(cache.batches)
        builds = build.call_count
        with patch.object(cache, "_polygon_rows", wraps=cache._polygon_rows) as rasterize:
            cache.update(path, 5)
            cache.draw((1, 1, 1, 0.16))
            rasterize.assert_not_called()
            assert build.call_count == builds
            path.append((10, 800))
            cache.update(path, 5)
            assert rasterize.call_count == 2
            assert all(len(call.args[0]) <= 2 for call in rasterize.call_args_list)
        cache.draw((1, 1, 1, 0.16))
        changed = {chunk for chunk, batches in initial.items() if cache.batches[chunk] is not batches}
        assert len(changed) <= 2
        assert len(initial) > 10
