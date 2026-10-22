from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys

import bpy
import pytest
from mathutils import Matrix, Vector

from anyimage.operators.cutout_tool.preview import CutoutGridPreview, screen_to_grid_matrix


@pytest.mark.parametrize("perspective", [
    Matrix.Identity(4),
    Matrix(((1.4, 0, 0, 0), (0, 1.8, 0, 0), (0, 0, -1, -0.2), (0, 0, -1, 0))),
])
def test_preview_spacing_tracks_world_distance_under_projection(perspective):
    world = (Matrix.Translation((0.2, -0.1, -5)) @ Matrix.Rotation(0.6, 4, "Y")
             @ Matrix(((2, 0.4, 0, 0), (0, 3, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))))
    size = (1200, 800)
    points = [Vector((x, y, 0, 1)) for x, y in ((0, 0), (0.1, 0), (0, 0.2), (0.3, -0.4))]
    edge_length = 0.1
    transform = screen_to_grid_matrix(size, perspective, world, edge_length)
    grid_points = []
    for point in points:
        clip = perspective @ world @ point
        screen = Vector(((clip.x / clip.w + 1) * size[0] / 2,
                         (clip.y / clip.w + 1) * size[1] / 2, 1))
        grid = transform @ screen
        grid_points.append(Vector((grid.x / grid.z, grid.y / grid.z)))
    for point, grid in zip(points[1:], grid_points[1:]):
        actual = (grid - grid_points[0]).length * edge_length
        expected = (world @ point - world @ points[0]).to_3d().length
        assert actual == pytest.approx(expected, rel=1e-5)


def test_edge_on_preview_rejects_projection():
    world = Matrix(((0, 0, 1, 0), (0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 0, 1)))
    with pytest.raises(ValueError):
        screen_to_grid_matrix((100, 100), Matrix.Identity(4), world, 0.1)


def test_preview_reuses_gpu_resources_when_view_or_density_changes():
    shader, batch = Mock(), Mock()
    build = Mock(return_value=batch)
    gpu = SimpleNamespace(
        types=SimpleNamespace(GPUStageInterfaceInfo=Mock(), GPUShaderCreateInfo=Mock()),
        shader=SimpleNamespace(create_from_info=Mock(return_value=shader)),
        state=SimpleNamespace(blend_set=Mock()),
        matrix=SimpleNamespace(get_projection_matrix=lambda: Matrix.Identity(4),
                               get_model_view_matrix=lambda: Matrix.Identity(4)),
    )
    preview = CutoutGridPreview()
    triangles = ((0, 0), (100, 0), (0, 100))
    with patch.dict(sys.modules, {"gpu": gpu, "gpu_extras.batch": SimpleNamespace(batch_for_shader=build)}):
        preview.draw(triangles, (1, 1, 1, 0.16), Matrix.Identity(3))
        preview.draw(triangles, (1, 1, 1, 0.16), Matrix.Scale(2, 3))
        assert build.call_count == gpu.shader.create_from_info.call_count == 1
        preview.draw(((0, 0), (200, 0), (0, 100)), (1, 1, 1, 0.16), Matrix.Identity(3))
        assert build.call_count == 2
        batch.draw.side_effect = RuntimeError("draw failed")
        with pytest.raises(RuntimeError, match="draw failed"):
            preview.draw(preview.triangles, (1, 1, 1, 0.16), Matrix.Identity(3))
    gpu.state.blend_set.assert_called_with("NONE")
