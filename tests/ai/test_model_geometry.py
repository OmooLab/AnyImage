from unittest.mock import patch
import numpy as np


from anyimage.server.models import moge as moge2_model


def test_moge_infer_returns_geometry_frame_with_model_validity():
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

    with patch.object(moge2_model, "infer_one", return_value=prediction):
        frame = moge2_model.infer(None, {}, "image", include_points=True)

    assert np.array_equal(frame.validity, mask.astype(np.float32))
    assert np.array_equal(frame.normal, prediction["normal"])
    assert np.array_equal(frame.points, prediction["points"])
    assert np.array_equal(
        frame.intrinsics,
        np.asarray(((2.0, 0.0, 1.0), (0.0, 2.0, 1.0), (0.0, 0.0, 1.0))),
    )


def test_moge_frame_omits_points_when_not_requested():
    prediction = {
        "depth": np.ones((2, 2), dtype=np.float32),
        "normal": np.zeros((2, 2, 3), dtype=np.float32),
        "mask": np.ones((2, 2), dtype=bool),
        "intrinsics": np.eye(3, dtype=np.float32),
        "points": np.ones((2, 2, 3), dtype=np.float32),
    }

    with patch.object(moge2_model, "infer_one", return_value=prediction):
        frame = moge2_model.infer(None, {}, "image", include_points=False)

    assert frame.points is None
    assert frame.validity.all()
