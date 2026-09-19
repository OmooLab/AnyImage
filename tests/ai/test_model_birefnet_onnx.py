from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from server.models import onnx_birefnet


@pytest.mark.parametrize("size", [1024, 2048])
def test_probability_alpha_keeps_transparency_and_source_dimensions(size):
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="image", shape=[1, 3, size, size])],
        get_outputs=lambda: [SimpleNamespace(name="alpha")],
    )
    mask = np.full((1, 1, size, size), 0.37, dtype=np.float32)
    with patch.object(onnx_birefnet, "run_session", return_value=[mask]) as run:
        result = onnx_birefnet.infer_alpha(session, Image.new("RGB", (31, 17), (64, 128, 192)), release_memory=False)
    assert result.shape == (17, 31)
    assert result.dtype == np.float32
    np.testing.assert_allclose(result, 0.37, atol=1e-6)
    assert run.call_args.kwargs["release_memory"] is False
    feed = run.call_args.args[2]["image"]
    np.testing.assert_allclose(feed[0, :, 0, 0], (np.array([64, 128, 192]) / 255 - [.485, .456, .406]) / [.229, .224, .225], atol=1e-6)
