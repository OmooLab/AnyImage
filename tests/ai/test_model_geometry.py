from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np


from server.models import geometry


def test_geometry_frame_explicitly_converts_normalized_intrinsics():
    intrinsics = np.array(((0.8, 0, 1.2), (0, 0.7, -0.1), (0, 0, 1)), np.float32)
    result = geometry._pixel_intrinsics(intrinsics, (100, 50))
    np.testing.assert_allclose(result, ((80, 0, 120), (0, 35, -5), (0, 0, 1)), rtol=1e-6)
    assert intrinsics[0, 0] == np.float32(0.8)


def test_geometry_inference_preserves_model_fields():
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

    adapter = SimpleNamespace(infer=Mock(return_value=prediction))
    frame = geometry.infer_geometry(adapter, object(), np.zeros((2, 2, 3), np.float32), 9)

    assert np.array_equal(frame.validity, mask.astype(np.float32))
    assert np.array_equal(frame.normal, prediction["normal"])
    np.testing.assert_array_equal(frame.points, prediction["points"])
    assert np.array_equal(
        frame.intrinsics,
        np.asarray(((2.0, 0.0, 1.0), (0.0, 2.0, 1.0), (0.0, 0.0, 1.0))),
    )
