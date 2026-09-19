from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from PIL import Image


from server.geometry import prediction_artifacts as artifacts
from server.models.geometry import GeometryFrame
from server.models.onnx_moge2 import depth_to_points


def make_frame(depth):
    depth = np.asarray(depth, dtype=np.float32)
    height, width = depth.shape
    normalized = np.array([[1.2, 0, 0.4], [0, 1.4, 0.6], [0, 0, 1]], np.float32)
    intrinsics = normalized.copy()
    intrinsics[0] *= width
    intrinsics[1] *= height
    return GeometryFrame(
        depth=depth,
        validity=np.ones_like(depth),
        intrinsics=intrinsics,
        points=depth_to_points(depth, normalized),
        normal=np.zeros((*depth.shape, 3), np.float32),
    )


def silhouette():
    alpha = np.zeros((25, 35), np.float32)
    alpha[4:21, 4:22] = 1
    alpha[4:21, 22:25] = 0.2
    depth = np.full(alpha.shape, 20, np.float32)
    depth[alpha == 1] = 2
    return make_frame(depth), alpha


def test_alpha_resize_retains_threshold_values(tmp_path):
    rgba = np.zeros((1, 4, 4), np.uint8)
    rgba[0, :, 3] = [25, 26, 242, 243]
    path = tmp_path / "alpha.png"
    Image.fromarray(rgba).save(path)
    alpha = artifacts._image_alpha(path, (2, 8))
    np.testing.assert_array_equal(
        alpha >= 0.1, [[False] * 2 + [True] * 6] * 2
    )
    np.testing.assert_array_equal(
        alpha >= 0.95, [[False] * 6 + [True] * 2] * 2
    )


@pytest.mark.parametrize(
    "generate_depth,normal_mode",
    [
        (True, "OBJECT"),
        (True, "TANGENT"),
        (True, "NONE"),
        (False, "OBJECT"),
    ],
)
def test_artifacts_write_raw_requested_depth_and_preserve_normals(
    tmp_path, generate_depth, normal_mode
):
    frame, alpha = silhouette()
    rgba = np.full((*alpha.shape, 4), 255, np.uint8)
    rgba[..., 3] = np.round(alpha * 255).astype(np.uint8)
    path = tmp_path / "source.png"
    Image.fromarray(rgba).save(path)
    context = SimpleNamespace(
        directory=tmp_path,
        resource=lambda _: None,
        progress=lambda *_: None,
        check_cancelled=lambda: None,
    )
    with (
        patch.object(artifacts.moge, "infer", return_value=frame) as infer,
        patch.object(
            artifacts, "write_depth_texture",
            return_value=tmp_path / "depth.exr",
        ) as depth,
        patch.object(
            artifacts, "write_depth_metadata", return_value=tmp_path / "depth.json"
        ) as metadata,
        patch.object(
            artifacts, "_write_normal", return_value=tmp_path / "normal.png"
        ) as normal,
    ):
        artifacts.generate_moge_artifacts(
            context, {}, path, generate_depth=generate_depth, normal_mode=normal_mode,
        )
    infer.assert_called_once()
    if normal_mode != "NONE":
        assert normal.call_args.args[0] is frame
    else:
        normal.assert_not_called()
    if generate_depth:
        written_frame = depth.call_args.args[0]
        np.testing.assert_array_equal(depth.call_args.kwargs["alpha"], alpha)
        assert metadata.call_args.args[0] is written_frame
        assert written_frame is frame
        assert frame.depth[12, 24] == 20
    else:
        metadata.assert_not_called()
        depth.assert_not_called()
