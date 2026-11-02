from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from PIL import Image


from server.geometry import prediction_artifacts as artifacts
from server.models.geometry import GeometryFrame
from server.models.moge_geometry import depth_to_points


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
    context = SimpleNamespace(
        directory=tmp_path,
        resource=lambda _: None,
        progress=lambda *_: None,
        check_cancelled=lambda: None,
    )
    with (
        patch.object(artifacts.moge, "infer", return_value=make_frame(np.ones((2, 8)))),
        patch.object(artifacts, "write_depth_texture") as depth,
        patch.object(artifacts, "write_depth_metadata"),
    ):
        artifacts.generate_moge_artifacts(context, {}, path, generate_depth=True)
    alpha = depth.call_args.kwargs["alpha"]
    np.testing.assert_array_equal(
        alpha >= 0.1, [[False] * 2 + [True] * 6] * 2
    )
    np.testing.assert_array_equal(
        alpha >= 0.95, [[False] * 6 + [True] * 2] * 2
    )


def test_source_is_closed_before_cancelled_inference(tmp_path):
    path = tmp_path / "source.png"
    Image.new("RGBA", (4, 4)).save(path)
    context = SimpleNamespace(
        directory=tmp_path,
        resource=lambda _: None,
        progress=lambda *_: None,
        check_cancelled=lambda: None,
    )
    with Image.open(path) as source:
        def cancel(*_args, **_kwargs):
            assert source.fp is None
            raise RuntimeError("cancelled")

        with (
            patch.object(artifacts, "open_image", return_value=source),
            patch.object(artifacts.moge, "infer", side_effect=cancel),
            pytest.raises(RuntimeError, match="cancelled"),
        ):
            artifacts.generate_moge_artifacts(context, {}, path, generate_depth=True)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "generate_depth,generate_normal",
    [(True, True), (True, False), (False, True)],
)
def test_artifacts_write_raw_requested_depth_and_preserve_normals(
    tmp_path, generate_depth, generate_normal
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
            artifacts, "write_normal_texture", return_value=tmp_path / "normal.png"
        ) as normal,
    ):
        artifacts.generate_moge_artifacts(
            context, {}, path, generate_depth=generate_depth, generate_normal=generate_normal,
        )
    infer.assert_called_once()
    if generate_normal:
        assert normal.call_args.args[0] is frame
        np.testing.assert_array_equal(normal.call_args.args[1], alpha >= 0.1)
        assert normal.call_args.args[2] == (35, 25)
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
