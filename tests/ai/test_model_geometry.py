from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
import pytest
from PIL import Image


from server.models import moge


@pytest.mark.parametrize("include_points", [True, False])
def test_moge_infer_returns_geometry_frame_with_model_validity(include_points):
    mask = np.asarray(((1.0, 0.2), (0.7, 0.0)), dtype=np.float32)
    prediction = {
        "depth": np.ones((2, 2), dtype=np.float32),
        "normal": np.zeros((2, 2, 3), dtype=np.float32),
        "mask": mask,
        "intrinsics": np.asarray(
            ((1.0, 0.0, 0.5), (0.0, 1.0, 0.5), (0.0, 0.0, 1.0)),
            dtype=np.float32,
        ),
        "points": np.ones((2, 2, 3), dtype=np.float32),
    }

    model = object()
    manager = SimpleNamespace(get_session=Mock(return_value=(model, 0.0)))
    adapter = SimpleNamespace(infer=Mock(return_value=prediction))
    image = Image.new("RGB", (2, 2), (255, 128, 0))
    parameters = {"model": "MOGE2", "device": "cpu", "resolution_level": "9"}
    with patch.object(moge, "model_adapter", return_value=adapter):
        frame = moge.infer(manager, parameters, image, include_points=include_points)

    manager.get_session.assert_called_once_with("MOGE2", "cpu")
    assert adapter.infer.call_args.args[0] is model
    np.testing.assert_array_equal(
        adapter.infer.call_args.args[1], np.asarray(image, dtype=np.float32) / 255.0,
    )
    assert adapter.infer.call_args.args[2] == 9
    assert adapter.infer.call_args.kwargs == {
        "release_memory": True, "include_points": include_points,
    }

    assert np.array_equal(frame.validity, mask.astype(np.float32))
    assert np.array_equal(frame.normal, prediction["normal"])
    if include_points:
        assert np.array_equal(frame.points, prediction["points"])
    else:
        assert frame.points is None
    assert np.array_equal(
        frame.intrinsics,
        np.asarray(((2.0, 0.0, 1.0), (0.0, 2.0, 1.0), (0.0, 0.0, 1.0))),
    )


def test_moge_checks_cancellation_before_loading_model():
    manager = SimpleNamespace(get_session=Mock())
    with pytest.raises(RuntimeError, match="cancelled"):
        moge.infer(
            manager, {}, Image.new("RGB", (2, 2)), include_points=False,
            cancel_check=Mock(side_effect=RuntimeError("cancelled")),
        )
    manager.get_session.assert_not_called()
