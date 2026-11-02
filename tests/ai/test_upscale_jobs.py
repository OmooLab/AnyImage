from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PIL import Image

import server
from server.jobs import upscale
from server.models import onnx_upscale
from server.models.onnx_runtime import OnnxResourceError
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("key", [
    "REALESRGAN_GENERAL_WDN_X4V3", "HAT_GAN_X4_SHARPER", "REALESRGAN_X4PLUS",
])
def test_upscale_models_resize_prediction_then_restore_alpha(tmp_path, key):
    rng = np.random.default_rng(1)
    source = Image.fromarray(rng.integers(0, 256, (5, 7, 4), dtype=np.uint8))
    path = tmp_path / "source.png"
    source.save(path)
    prediction = Image.fromarray(rng.integers(0, 256, (20, 28, 3), dtype=np.uint8))
    context = FakeJobContext(tmp_path / "job", "upscale_image")
    with patch.object(onnx_upscale, "infer", return_value=prediction) as infer:
        result = upscale.run(context, {"input": str(path), "model": key, "device": "cpu"})
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
    path = tmp_path / "input.png"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(path)
    context = FakeJobContext(tmp_path / "job", "upscale_image")
    with patch.object(onnx_upscale, "infer", return_value=Image.new("RGB", (16, 16))) as infer:
        result = upscale.run(context, {
            "input": str(path), "model": "REALESRGAN_GENERAL_WDN_X4V3", "device": "cpu",
        })
    infer.assert_called_once()
    assert list(context.directory.iterdir()) == [context.directory / "upscale.png"]
    with Image.open(context.directory / result["upscale"]) as output:
        assert output.mode == "RGB"
        assert output.size == (8, 8)
    assert (
        "INFO", "Upscale model: REALESRGAN_GENERAL_WDN_X4V3; maximum AI input size: 2048 px",
    ) in context.logs


def test_upscale_resource_error_closes_input_and_reaches_job_boundary(tmp_path):
    path = tmp_path / "input.png"
    Image.new("RGB", (8, 8)).save(path)
    manager = SimpleNamespace(get_session=lambda *_: (object(), 0.0), clear=Mock())
    context = FakeJobContext(tmp_path / "job", "upscale_image", manager)
    source = Image.open(path)
    try:
        with (
            patch.object(upscale, "open_image", return_value=source),
            patch.object(onnx_upscale, "infer", side_effect=OnnxResourceError("provider memory exhausted")),
            pytest.raises(OnnxResourceError, match="provider memory exhausted"),
        ):
            server.upscale_image(context, {
                "input": str(path), "model": "REALESRGAN_GENERAL_WDN_X4V3", "device": "directml",
            })
        assert source.fp is None
    finally:
        source.close()
    assert list(context.directory.iterdir()) == []
    manager.clear.assert_called_once_with()


def test_upscale_output_allocation_failure_clears_cache_at_job_boundary(tmp_path):
    path = tmp_path / "input.png"
    Image.new("RGB", (2, 2)).save(path)
    manager = SimpleNamespace(get_session=lambda *_: (object(), 0.0), clear=Mock())
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
    manager.clear.assert_called_once_with()
