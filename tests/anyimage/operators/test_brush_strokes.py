import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
import pytest


from anyimage.common import selection, viewport
from anyimage.operators import mask_tool as mask


def test_simplified_segments_bound_every_original_sample():
    raw = [(float(x), float(20 * np.sin(x / 15))) for x in np.arange(0, 160, 0.2)]
    path, samples = [], []
    for point in raw:
        viewport.append_lasso_point(path, point, samples)
    assert len(path) < len(raw) / 5
    for start, end in zip(path, path[1:]):
        segment = np.array(end) - start
        points = np.array([point for point in raw if start[0] <= point[0] <= end[0]])
        factor = np.clip((points - start) @ segment / (segment @ segment), 0, 1)
        distances = np.linalg.norm(points - (np.array(start) + factor[:, None] * segment), axis=1)
        assert distances.max() <= 0.75 + 1e-10


@pytest.mark.parametrize("radius", [2, 5, 25])
@pytest.mark.parametrize("path", [
    ((40, 70), (70, 70), (70, 100)),
    ((35, 35), (100, 100), (35, 100), (100, 35)),
])
def test_brush_antialiases_the_hard_union_once(radius, path):
    size = (150, 150)
    hard = np.zeros(size[::-1], dtype=bool)
    for polygon in viewport.brush_footprint_polygons(path, radius):
        hard |= selection._rasterize_path((0, 0, *size), polygon)
    result = mask.rasterize_brush_path(size, path, radius, lambda points: points)
    np.testing.assert_allclose(result.full_values(size), selection._antialias_mask(hard))
    assert result.values.size < size[0] * size[1]


@pytest.mark.parametrize("radius", [2, 5, 25])
def test_straight_stroke_is_independent_of_segmentation(radius):
    size = (160, 160)
    sparse = ((40, 70), (110, 70))
    dense = tuple((x, 70) for x in range(40, 111, 5))
    results = [mask.rasterize_brush_path(size, path, radius, lambda p: p).full_values(size)
               for path in (sparse, dense)]
    np.testing.assert_array_equal(*results)


def test_incremental_preview_matches_full_union_when_tail_moves_and_crosses():
    cache = viewport.BrushPreview()
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
                     for bottom, _, intervals in viewport.scanline_union_bands(
                         viewport.brush_footprint_polygons(path, 8), cache.step)
                     if intervals}
        assert cache.coverage.keys() == reference.keys()
        for row in reference:
            np.testing.assert_allclose(cache.coverage[row], reference[row], atol=1e-10)


def test_preview_reuses_batches_and_limits_updates_to_changed_rows():
    cache = viewport.BrushPreview()
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


@pytest.mark.parametrize("exit_kind", ["ESC", "SWITCH", "ERROR", "COMPLETE"])
def test_gesture_releases_preview_and_samples_on_every_exit(exit_kind):
    gesture = viewport.ImageGesture()
    gesture.gesture = "BRUSH"
    gesture.active_tool_id = "anyimage.mask"
    gesture._path = [(0, 0), (10, 10)]
    gesture._path_samples = list(gesture._path)
    gesture._brush_preview = viewport.BrushPreview()
    handle = gesture._handle = object()
    gesture._brush_preview.update(gesture._path, 5)
    context = SimpleNamespace(workspace=Mock(), area=Mock())
    event = SimpleNamespace(type="ESC" if exit_kind == "ESC" else "LEFTMOUSE",
                            value="PRESS" if exit_kind == "ESC" else "RELEASE",
                            mouse_region_x=10, mouse_region_y=10)
    gesture.report = Mock()
    def complete(context):
        if exit_kind == "ERROR":
            raise ValueError("Failed projection")
        gesture._finish(context)
        return {"FINISHED"}
    gesture._complete = complete
    tool = "builtin.select" if exit_kind == "SWITCH" else gesture.active_tool_id
    remove = Mock()
    fake_bpy = SimpleNamespace(types=SimpleNamespace(SpaceView3D=SimpleNamespace(draw_handler_remove=remove)))
    with patch.object(viewport, "active_view3d_tool_id", return_value=tool), patch.object(viewport, "bpy", fake_bpy):
        result = gesture.modal(context, event)
        gesture._finish(context)
    remove.assert_called_once_with(handle, "WINDOW")
    assert gesture._handle is None
    assert result == ({"FINISHED"} if exit_kind == "COMPLETE" else {"CANCELLED"})
    assert gesture._path is gesture._path_samples is gesture._brush_preview is None
    assert gesture._fill_triangles == gesture._outline_segments == ()
    assert viewport.ImageGesture()._brush_preview is None
