from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import pytest
from blendjob.server import JobCancelled

from server.jobs import remove_background
from server.models import onnx_ben2
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("checkpoint", [1, 2, 3])
@pytest.mark.parametrize("output_kind", ["alpha", "foreground"])
def test_background_job_propagates_cancellation(tmp_path, checkpoint, output_kind):
    path = tmp_path / "input.png"
    Image.new("RGBA", (2, 2)).save(path)
    manager = Mock()
    manager.get_session.return_value = (object(), 0.0)
    context = FakeJobContext(tmp_path / "job", "remove_background", manager)
    context.check_cancelled = Mock(
        side_effect=[None] * checkpoint + [JobCancelled("Job cancelled")],
    )
    source = Image.open(path)
    try:
        with (
            patch.object(remove_background, "open_image", return_value=source),
            patch.object(onnx_ben2, "infer_alpha", return_value=np.ones((2, 2))) as infer,
            pytest.raises(JobCancelled),
        ):
            remove_background.run(context, {
                "input": str(path), "model": "BEN2_BASE", "device": "cpu",
                "output_kind": output_kind,
            })
        assert source.fp is None
    finally:
        source.close()
    assert manager.get_session.call_count == int(checkpoint > 1)
    assert infer.call_count == int(checkpoint > 2)
    assert list(context.directory.iterdir()) == []


@pytest.mark.parametrize("failure", ["cancel", "prediction", "sequence", "output_kind"])
def test_alpha_job_failure_does_not_write_result(tmp_path, failure):
    source = tmp_path / "input.png"
    Image.new("RGB", (2, 2)).save(source)
    context = FakeJobContext(tmp_path / "job", "remove_background")
    parameters = {"input": str(source), "model": "BEN2_BASE", "device": "cpu", "output_kind": "alpha"}
    if failure == "sequence":
        frames = tmp_path / "frames"
        frames.mkdir()
        for i in (1, 2):
            Image.new("RGB", (2, 2)).save(frames / f"{i}.png")
        parameters["input"] = str(frames)
    if failure == "output_kind":
        parameters["output_kind"] = "invalid"

    def infer(*args, **kwargs):
        if failure == "prediction":
            raise RuntimeError("Prediction failed")
        context.check_cancelled = lambda: (_ for _ in ()).throw(RuntimeError("Cancelled"))
        return np.ones((2, 2), np.float32)

    with patch.object(onnx_ben2, "infer_alpha", side_effect=infer):
        with pytest.raises((RuntimeError, ValueError)):
            remove_background.run(context, parameters)
    assert not (context.directory / "alpha.npy").exists()
