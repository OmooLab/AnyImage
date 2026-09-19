from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest

from server.jobs import remove_background
from server.models import onnx_ben2
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("failure", ["cancel", "prediction", "sequence", "output_kind"])
def test_alpha_job_failure_does_not_write_result(tmp_path, failure):
    source = tmp_path / "input.png"
    Image.new("RGB", (2, 2)).save(source)
    context = FakeJobContext(tmp_path / "job", "remove-background")
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

    with patch.object(onnx_ben2, "create_session", return_value=object()), patch.object(onnx_ben2, "infer_alpha", side_effect=infer):
        with pytest.raises((RuntimeError, ValueError)):
            remove_background.run(context, parameters)
    assert not (context.directory / "alpha.npy").exists()
