from anyimage.common.image_preview import preview_draw_bounds

import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

from anyimage.common.image_preview import create_preview_texture, draw_preview_texture
from anyimage.common import image_preview


def test_preview_is_centered_at_requested_aspect():
    left, bottom, width, height = preview_draw_bounds((1000, 800), 2.0)

    assert width / height == 2.0
    assert left + width * 0.5 == 500.0
    assert bottom + height * 0.5 == 400.0


def test_preview_encodes_linear_pixels_once_and_preserves_straight_alpha():
    rgba = np.asarray([
        [[0.0, 0.18, 1.0, 0.5], [2.0, -0.1, 0.5, 0.0]],
        [[1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 0.25]],
    ], dtype=np.float32)
    before = rgba.copy()
    texture = Mock()
    gpu = SimpleNamespace(types=SimpleNamespace(
        Buffer=lambda _format, _size, pixels: pixels.copy(),
        GPUTexture=Mock(return_value=texture),
    ))
    with patch.dict(sys.modules, {"gpu": gpu}):
        assert create_preview_texture(rgba) is texture
    options = gpu.types.GPUTexture.call_args.kwargs
    assert gpu.types.GPUTexture.call_args.args == ((2, 2),)
    assert options["format"] == "RGBA32F"
    displayed = np.flipud(options["data"].reshape((2, 2, 4)))
    np.testing.assert_allclose(displayed[0, 0], (0.0, 0.461356, 1.0, 0.5), atol=1e-6)
    np.testing.assert_allclose(displayed[0, 1], (1.0, 0.0, 0.735357, 0.0), atol=1e-6)
    np.testing.assert_allclose(displayed[1], rgba[1], atol=1e-6)
    np.testing.assert_array_equal(rgba, before)


@pytest.mark.parametrize("fails", [False, True])
def test_preview_draw_uses_encoded_pixels_and_restores_blending(fails):
    batch = Mock()
    batch.draw.side_effect = RuntimeError("draw failed") if fails else None
    build = Mock(return_value=batch)
    shader = Mock()
    blend = Mock()
    modules = {
        "gpu": SimpleNamespace(
            state=SimpleNamespace(blend_set=blend),
            matrix=SimpleNamespace(get_projection_matrix=lambda: np.eye(4),
                                   get_model_view_matrix=lambda: np.eye(4)),
        ),
        "gpu_extras.batch": SimpleNamespace(batch_for_shader=build),
    }
    texture = object()
    with patch.dict(sys.modules, modules), patch.object(image_preview, "_preview_shader", return_value=shader):
        if fails:
            with pytest.raises(RuntimeError, match="draw failed"):
                draw_preview_texture(texture, (10, 20, 30, 40))
        else:
            draw_preview_texture(texture, (10, 20, 30, 40))
    batch.draw.assert_called_once_with(shader)
    shader.uniform_sampler.assert_called_once_with("image", texture)
    assert build.call_args.args[2]["pos"] == ((10, 20), (40, 20), (40, 60), (10, 60))
    assert [call.args[0] for call in blend.call_args_list] == ["ALPHA", "NONE"]
