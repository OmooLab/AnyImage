import unittest
from unittest.mock import patch

import numpy as np

from server.models import moge_geometry


class MogeGeometryTest(unittest.TestCase):
    def test_postprocess_recovers_camera_projection_and_metric_scale(self):
        height, width = 64, 80
        focal = np.float32(0.9)
        shift = np.float32(0.3)
        metric_scale = np.float32(2.0)
        uv = moge_geometry.normalized_view_plane_uv(width, height, np.float32)
        depth = np.linspace(1.0, 2.4, height * width, dtype=np.float32).reshape(
            height,
            width,
        )
        raw_points = np.concatenate(
            (uv * depth[..., None] / focal, (depth - shift)[..., None]),
            axis=-1,
        )
        raw = {
            "points": raw_points[None],
            "normal": np.broadcast_to(
                np.array((0.0, 0.0, 1.0), dtype=np.float32),
                (1, height, width, 3),
            ),
            "mask": np.ones((1, height, width), dtype=np.float32),
            "metric_scale": np.array((metric_scale,), dtype=np.float32),
        }

        raw["mask"][0, 0, :4] = [0.0, 0.2, 0.7, 1.0]
        result = moge_geometry.postprocess(raw)

        np.testing.assert_allclose(result["depth"], depth * metric_scale, rtol=1e-3)
        np.testing.assert_allclose(result["points"][..., 2], result["depth"], rtol=1e-5)
        np.testing.assert_array_equal(result["mask"], raw["mask"][0])

    def test_postprocess_preserves_mask_for_nonpositive_depth(self):
        mask = np.array([[[0.2, 0.7], [0.0, 1.0]]], dtype=np.float32)
        raw = {
            "points": np.zeros((1, 2, 2, 3), dtype=np.float32),
            "normal": np.zeros((1, 2, 2, 3), dtype=np.float32),
            "mask": mask,
            "metric_scale": np.ones(1, dtype=np.float32),
        }
        with patch.object(moge_geometry, "recover_focal_shift", return_value=(1.0, -1.0)) as recover:
            result = moge_geometry.postprocess(raw)
        np.testing.assert_array_equal(recover.call_args.args[1], mask[0] > 0.5)
        np.testing.assert_array_equal(result["mask"], mask[0])
        self.assertTrue((result["depth"] < 0).all())


def test_postprocess_can_skip_point_reconstruction():

    raw = {
        "points": np.ones((1, 2, 2, 3), np.float32),
        "normal": np.ones((1, 2, 2, 3), np.float32),
        "mask": np.ones((1, 2, 2), np.float32),
        "metric_scale": np.ones(1, np.float32),
    }
    with patch.object(moge_geometry, "recover_focal_shift", return_value=(1.0, 0.0)), patch.object(moge_geometry, "depth_to_points", side_effect=AssertionError("Unexpected point reconstruction")):
        result = moge_geometry.postprocess(raw, include_points=False)
    assert result["points"] is None
    assert result["depth"].shape == (2, 2)
