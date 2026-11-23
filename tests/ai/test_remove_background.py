from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import pytest
from blendjob.server import JobCancelled

from server.jobs import remove_background
from server.model_manager import ModelManager
from server.models import model_adapter, onnx_ben2
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("checkpoint", [1, 2, 3])
def test_background_job_propagates_cancellation(tmp_path, checkpoint):
    path = tmp_path / "input.npy"
    np.save(path, np.zeros((2, 2, 4), np.uint8))
    manager = Mock()
    manager.get_session.return_value = (object(), 0.0)
    context = FakeJobContext(tmp_path / "job", "remove_background", manager)
    context.check_cancelled = Mock(
        side_effect=[None] * checkpoint + [JobCancelled("Job cancelled")],
    )
    with (
        patch.object(onnx_ben2, "infer_alpha", return_value=np.ones((2, 2))) as infer,
        pytest.raises(JobCancelled),
    ):
        remove_background.run(context, {
            "input": str(path), "model": "BEN2_BASE", "device": "cpu",
        })
    assert manager.get_session.call_count == int(checkpoint > 1)
    assert infer.call_count == int(checkpoint > 2)
    assert list(context.directory.iterdir()) == []


@pytest.mark.parametrize("failure", ["cancel", "prediction", "sequence"])
def test_alpha_job_failure_does_not_write_result(tmp_path, failure):
    source = tmp_path / "input.npy"
    np.save(source, np.zeros((2, 2, 4), np.uint8))
    context = FakeJobContext(tmp_path / "job", "remove_background")
    parameters = {"input": str(source), "model": "BEN2_BASE", "device": "cpu"}
    if failure == "sequence":
        frames = tmp_path / "frames"
        frames.mkdir()
        for i in (1, 2):
            Image.new("RGB", (2, 2)).save(frames / f"{i}.png")
        parameters["input"] = str(frames)

    def infer(*args, **kwargs):
        if failure == "prediction":
            raise RuntimeError("Prediction failed")
        context.check_cancelled = lambda: (_ for _ in ()).throw(RuntimeError("Cancelled"))
        return np.ones((2, 2), np.float32)

    with patch.object(onnx_ben2, "infer_alpha", side_effect=infer):
        with pytest.raises((RuntimeError, ValueError)):
            remove_background.run(context, parameters)
    assert not (context.directory / "alpha.npy").exists()


@pytest.mark.parametrize("key", ["BIREFNET_LITE", "BEN2_BASE", "BIREFNET_HR_MATTING"])
def test_models_dispatch_keep_alpha(tmp_path, key):
    source = tmp_path / "source.npy"
    np.save(source, np.full((5, 7, 4), (60, 120, 180, 128), np.uint8))
    manager = ModelManager(tmp_path / "models")
    context = FakeJobContext(tmp_path / "job", "remove_background", manager)
    adapter = model_adapter(key)
    parameters = {"input": str(source), "model": key, "device": "directml"}
    with patch.object(manager, "ready", return_value=True), patch.object(adapter, "create_session", return_value=object()) as create, patch.object(
        adapter, "infer_alpha", return_value=np.full((5, 7), .4, np.float32)
    ) as infer:
        remove_background.run(context, parameters)
    create.assert_called_once_with(manager.directory(key), "cpu" if key == "BIREFNET_HR_MATTING" else "directml")
    infer.assert_called_once()
    np.testing.assert_allclose(np.load(context.directory / "alpha.npy"), .4)
    manager.close()
    assert manager.snapshot()["loaded"]["background"] is None


def test_ben2_preserves_input_alpha_and_hides_transparent_rgb(tmp_path):
    path = tmp_path / "input.npy"
    np.save(path, np.array([[(255, 0, 0, 0), (0, 255, 0, 128)]], dtype=np.uint8))
    alpha = np.full((1, 2), 128 / 255, np.float32)
    context = FakeJobContext(tmp_path / "job", "remove_background")
    with patch.object(onnx_ben2, "infer_alpha", return_value=alpha) as infer:
        result = remove_background.run(context, {"input": str(path), "model": "BEN2_BASE", "device": "cpu"})
    np.testing.assert_array_equal(infer.call_args.args[1].convert("RGB"), [[(0, 0, 0), (0, 255, 0)]])
    np.testing.assert_array_equal(np.load(context.directory / result["alpha"]), alpha)


def test_background_alpha_job_preserves_float_precision(tmp_path):
    path = tmp_path / "input.npy"
    np.save(path, np.zeros((1, 2, 4), np.uint8))
    alpha = np.array([[0.123456, 0.987654]], dtype=np.float32)
    context = FakeJobContext(tmp_path / "result", "remove_background")
    with patch.object(onnx_ben2, "infer_alpha", return_value=alpha):
        result = remove_background.run(context, {"input": str(path), "model": "BEN2_BASE", "device": "cpu"})
    assert result == {"alpha": "alpha.npy"}
    np.testing.assert_array_equal(np.load(context.directory / result["alpha"], allow_pickle=False), alpha)
    assert not list(context.directory.glob("*.png"))
