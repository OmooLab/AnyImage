from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PIL import Image

import server
from server.jobs import upscale
from server.media.input import limit_image
from server.models import onnx_upscale
from server.models.onnx_runtime import OnnxResourceError
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("key", [
    "REALESRGAN_GENERAL_WDN_X4V3", "HAT_GAN_X4_SHARPER", "REALESRGAN_X4PLUS",
])
def test_upscale_models_resize_prediction_then_restore_alpha(tmp_path, key):
    rng = np.random.default_rng(1)
    source = Image.fromarray(rng.integers(0, 256, (5, 7, 4), dtype=np.uint8))
    path = tmp_path / "source.npy"
    np.save(path, np.asarray(source))
    prediction = Image.fromarray(rng.integers(0, 256, (20, 28, 3), dtype=np.uint8))
    context = FakeJobContext(tmp_path / "job", "upscale_image")
    with patch.object(onnx_upscale, "infer", return_value=prediction) as infer:
        result = upscale.run(context, {"input": str(path), "model": key, "device": "cpu"})
    np.testing.assert_array_equal(infer.call_args.args[1], source)
    assert infer.call_args.kwargs["tile_border"] == (48 if key == "HAT_GAN_X4_SHARPER" else 16)
    assert result == {"upscale": "upscale.png"}
    with Image.open(context.directory / result["upscale"]) as output:
        np.testing.assert_array_equal(
            output.convert("RGB"), prediction.resize((14, 10), Image.Resampling.LANCZOS),
        )
        np.testing.assert_array_equal(
            output.getchannel("A"), source.getchannel("A").resize((14, 10), Image.Resampling.LANCZOS),
        )


def test_rgb_upscale_job_writes_one_image_and_reports_settings(tmp_path):
    path = tmp_path / "input.npy"
    np.save(path, np.full((4, 4, 4), (10, 20, 30, 255), np.uint8))
    context = FakeJobContext(tmp_path / "job", "upscale_image")
    with patch.object(onnx_upscale, "infer", return_value=Image.new("RGB", (16, 16))) as infer:
        result = upscale.run(context, {
            "input": str(path), "model": "REALESRGAN_GENERAL_WDN_X4V3", "device": "cpu",
        })
    infer.assert_called_once()
    assert list(context.directory.iterdir()) == [context.directory / "upscale.png"]
    with Image.open(context.directory / result["upscale"]) as output:
        assert output.mode == "RGBA" and output.getchannel("A").getextrema() == (255, 255)
        assert output.size == (8, 8)
    assert (
        "INFO", "Upscale model: REALESRGAN_GENERAL_WDN_X4V3; maximum AI input size: 2048 px",
    ) in context.logs


def test_upscale_resource_error_reaches_job_boundary(tmp_path):
    path = tmp_path / "input.npy"
    np.save(path, np.zeros((8, 8, 4), np.uint8))
    manager = SimpleNamespace(get_session=lambda *_: (object(), 0.0), sessions=Mock())
    context = FakeJobContext(tmp_path / "job", "upscale_image", manager)
    with (
        patch.object(onnx_upscale, "infer", side_effect=OnnxResourceError("provider memory exhausted")),
        pytest.raises(OnnxResourceError, match="provider memory exhausted"),
    ):
        server.upscale_image(context, {
            "input": str(path), "model": "REALESRGAN_GENERAL_WDN_X4V3", "device": "directml",
        })
    assert list(context.directory.iterdir()) == []
    manager.sessions.close.assert_called_once_with()


def test_upscale_output_allocation_failure_clears_cache_at_job_boundary(tmp_path):
    path = tmp_path / "input.npy"
    np.save(path, np.zeros((2, 2, 4), np.uint8))
    manager = SimpleNamespace(get_session=lambda *_: (object(), 0.0), sessions=Mock())
    context = FakeJobContext(tmp_path / "job", "upscale_image", manager)
    padded = np.zeros((256, 256, 3), dtype=np.uint8)
    with (
        patch.object(onnx_upscale, "_pad_source", return_value=padded),
        patch.object(np, "empty", side_effect=MemoryError),
        pytest.raises(RuntimeError, match="exceeded available system memory"),
    ):
        server.upscale_image(context, {
            "input": str(path), "model": "REALESRGAN_X4PLUS", "device": "cpu",
        })
    assert list(context.directory.iterdir()) == []
    manager.sessions.close.assert_called_once_with()


def test_upscale_input_uses_the_global_long_edge_limit():
    assert limit_image(Image.new("RGB", (3000, 1500)), 2048).size == (2048, 1024)
    small = Image.new("RGB", (800, 600))
    assert limit_image(small, 2048).size == (800, 600)
    with pytest.raises(ValueError, match="between 1 and 8192"):
        limit_image(small, 9000)
