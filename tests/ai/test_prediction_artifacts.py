from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PIL import Image

from server.geometry import prediction_artifacts as artifacts
from server.jobs import cutout, depth_plane
from server.models import onnx_moge2
from server.models.moge_geometry import depth_to_points
from tests.anyimage.server.support import FakeJobContext


MODEL = {"model": "MOGE2_VITS_NORMAL", "device": "cpu", "resolution_level": 0}


def make_frame(depth):
    depth = np.asarray(depth, dtype=np.float32)
    height, width = depth.shape
    normalized = np.array([[1.2, 0, 0.4], [0, 1.4, 0.6], [0, 0, 1]], np.float32)
    intrinsics = normalized.copy()
    intrinsics[0] *= width
    intrinsics[1] *= height
    return artifacts.GeometryFrame(
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
    rgba = np.zeros((1, 4, 4), np.float32)
    rgba[0, :, 3] = [.0999, .1001, .9499, .9501]
    path = tmp_path / "alpha.npy"
    np.save(path, rgba)
    context = FakeJobContext(tmp_path, "generate_cutout_artifacts")
    with (
        patch.object(artifacts, "infer_geometry", return_value=make_frame(np.ones((2, 8)))),
        patch.object(artifacts, "write_depth_texture") as depth,
    ):
        artifacts.generate_moge_artifacts(context, {**MODEL, "input": str(path), "output_size": (4, 1)}, generate_depth=True)
    alpha = depth.call_args.kwargs["alpha"]
    np.testing.assert_array_equal(
        alpha >= 0.1, [[False] * 2 + [True] * 6] * 2
    )
    np.testing.assert_array_equal(
        alpha >= 0.95, [[False] * 6 + [True] * 2] * 2
    )


@pytest.mark.parametrize("generate_depth", [True, False])
def test_artifacts_write_normals_and_optional_depth(tmp_path, generate_depth):
    frame, alpha = silhouette()
    rgba = np.ones((*alpha.shape, 4), np.float32)
    rgba[..., 3] = alpha
    path = tmp_path / "source.npy"
    np.save(path, rgba)
    context = FakeJobContext(tmp_path, "generate_cutout_artifacts")
    with (
        patch.object(artifacts, "infer_geometry", return_value=frame) as infer,
        patch.object(onnx_moge2, "infer_normal", return_value=frame.normal) as infer_normal,
        patch.object(
            artifacts, "write_depth_texture",
            return_value=tmp_path / "depth.exr",
        ) as depth,
        patch.object(
            artifacts, "write_normal_texture", return_value=tmp_path / "normal.png"
        ) as normal,
    ):
        result = artifacts.generate_moge_artifacts(
            context, {**MODEL, "input": str(path), "output_size": (70, 50)}, generate_depth=generate_depth,
        )
    assert normal.call_args.args[0] is frame.normal
    np.testing.assert_array_equal(normal.call_args.args[1], alpha >= 0.1)
    assert normal.call_args.args[2] == (70, 50)
    if generate_depth:
        infer.assert_called_once()
        infer_normal.assert_not_called()
        written_frame = depth.call_args.args[0]
        np.testing.assert_array_equal(depth.call_args.kwargs["alpha"], alpha)
        assert result["intrinsics"] == frame.intrinsics.tolist()
        assert written_frame is frame
        assert frame.depth[12, 24] == 20
    else:
        infer_normal.assert_called_once()
        infer.assert_not_called()
        assert "intrinsics" not in result
        depth.assert_not_called()


def test_geometry_frame_explicitly_converts_normalized_intrinsics():
    intrinsics = np.array(((0.8, 0, 1.2), (0, 0.7, -0.1), (0, 0, 1)), np.float32)
    result = artifacts._pixel_intrinsics(intrinsics, (100, 50))
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
    frame = artifacts.infer_geometry(adapter, object(), np.zeros((2, 2, 3), np.float32), 9)

    assert np.array_equal(frame.validity, mask.astype(np.float32))
    assert np.array_equal(frame.normal, prediction["normal"])
    np.testing.assert_array_equal(frame.points, prediction["points"])
    assert np.array_equal(
        frame.intrinsics,
        np.asarray(((2.0, 0.0, 1.0), (0.0, 2.0, 1.0), (0.0, 0.0, 1.0))),
    )


def test_depth_alpha_multiplies_coverage_without_changing_geometry(tmp_path):
    validity = np.asarray([[0.75, 0, 1, 1]], dtype=np.float32)
    alpha = np.asarray([[0.8, 1, 0, 1]], dtype=np.float32)
    points = np.arange(12, dtype=np.float32).reshape(1, 4, 3)
    frame = artifacts.GeometryFrame(
        depth=points[..., 2], points=points,
        validity=validity.copy(), intrinsics=np.eye(3, dtype=np.float32),
    )
    output = tmp_path / "depth.exr"
    with patch.object(artifacts, "write_float_exr") as write:
        artifacts.write_depth_texture(frame, output, alpha=alpha)
        packed = write.call_args.args[0]
        np.testing.assert_allclose(packed[..., 3], [[0.6, 0, 0, 1]])
        np.testing.assert_array_equal(packed[..., :3], points)
        np.testing.assert_array_equal(frame.validity, validity)
        assert packed.dtype == np.float32
        with pytest.raises(ValueError, match="Alpha.*dimensions"):
            artifacts.write_depth_texture(frame, output, alpha=np.ones((4, 1)))
        assert write.call_count == 1


def test_normal_texture_matches_tangent_and_object_axes(tmp_path):
    output_path = tmp_path / "tangent-normal.png"
    camera_normals = np.asarray(
        [[
            (0.0, 0.0, -1.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, -1.0),
        ]],
        dtype=np.float32,
    )
    valid = np.asarray([[True, True, True, False]], dtype=bool)
    artifacts.write_normal_texture(
        camera_normals,
        valid,
        (4, 1),
        output_path,
    )

    with Image.open(output_path) as opened:
        encoded = np.asarray(opened, dtype=np.uint8)
    np.testing.assert_array_equal(
        encoded,
        np.asarray(
            [[
                (127, 127, 255),
                (255, 127, 127),
                (127, 0, 127),
                (128, 128, 255),
            ]],
            dtype=np.uint8,
        ),
    )
    artifacts.write_normal_texture(
        camera_normals, valid, (4, 1), output_path, normal_space="OBJECT",
    )
    with Image.open(output_path) as opened:
        encoded = np.asarray(opened, dtype=np.uint8)
    np.testing.assert_array_equal(encoded, [[
        (127, 0, 127),
        (255, 127, 127),
        (127, 127, 0),
        (128, 0, 128),
    ]])


def test_moge_model_input_preserves_rgb_independently_of_alpha(tmp_path):
    first_path = tmp_path / "first.npy"
    second_path = tmp_path / "second.npy"
    first = np.asarray(
        [[(240, 120, 60, 0), (200, 100, 50, 128), (9, 8, 7, 255)]],
        dtype=np.float32,
    ) / 255
    second = first.copy()
    second[..., 3] = 1
    np.save(first_path, first)
    np.save(second_path, second)
    context = FakeJobContext(tmp_path, "generate_cutout_artifacts")
    parameters = {"model": "MOGE2_VITS_NORMAL", "device": "cpu", "resolution_level": 0}

    for source in (first_path, second_path):
        with (
            patch.object(onnx_moge2, "infer_normal", side_effect=lambda session, rgb, level: rgb) as infer,
            patch.object(artifacts, "write_normal_texture"),
        ):
            artifacts.generate_moge_artifacts(
                context, {**parameters, "input": str(source), "output_size": (3, 1)}, generate_depth=False,
            )
        np.testing.assert_array_equal(infer.call_args.args[1], first[..., :3])


def test_moge_artifact_orchestration_uses_one_geometry_frame(tmp_path):
    input_path = tmp_path / "selection.npy"
    source = np.ones((4, 4, 4), np.float32)
    source[:2, 2:, 3] = 0
    np.save(input_path, source)
    output_directory = tmp_path / "job"
    output_directory.mkdir()
    context = FakeJobContext(output_directory, "generate_depth_plane_geometry")
    frame = artifacts.GeometryFrame(
        depth=np.ones((2, 2), dtype=np.float32),
        validity=np.ones((2, 2), dtype=np.float32),
        intrinsics=np.eye(3, dtype=np.float32),
        normal=np.zeros((2, 2, 3), dtype=np.float32),
        points=np.ones((2, 2, 3), dtype=np.float32),
    )

    with (
        patch.object(artifacts, "infer_geometry", return_value=frame) as infer,
        patch.object(artifacts, "write_float_exr", wraps=artifacts.write_float_exr) as write,
    ):
        result = artifacts.generate_moge_artifacts(
            context,
            {"input": str(input_path), "output_size": (4, 4), "model": "MOGE2_VITS_NORMAL", "resolution_level": 1, "device": "cpu"},
            generate_depth=True,
        )

    np.testing.assert_array_equal(write.call_args.args[0][..., 3], [[1, 0], [1, 1]])
    np.testing.assert_array_equal(frame.validity, np.ones((2, 2)))
    assert result == {
        "depth": "depth.exr",
        "intrinsics": frame.intrinsics.tolist(),
        "tangent_normal": "tangent-normal.png",
    }
    assert {path.name for path in output_directory.iterdir()} == {"depth.exr", "tangent-normal.png"}
    infer.assert_called_once()


def test_generate_cutout_artifacts_only_returns_requested_outputs(tmp_path):
    input_path = tmp_path / "input.npy"
    context = SimpleNamespace(
        directory=tmp_path / "job",
        progress=lambda *_args: None,
        check_cancelled=lambda: None,
    )
    parameters = {"input": str(input_path), "generate_depth": True}
    with patch.object(cutout, "generate_moge_artifacts") as generate:
        assert cutout.run(context, parameters) is generate.return_value

    generate.assert_called_once_with(
        context,
        {
            "input": str(input_path),
            "generate_depth": True,
        },
        generate_depth=True,
        normal_space="OBJECT",
    )


@pytest.mark.parametrize("plane_type,normal_space", [("DEPTH", "OBJECT"), ("RELIEF", "TANGENT")])
def test_plane_job_requests_matching_normal_space(tmp_path, plane_type, normal_space):
    context = FakeJobContext(tmp_path / "result", "generate_depth_plane_geometry")
    parameters = {"input": str(tmp_path / "input.npy"), "plane_type": plane_type}
    with patch.object(depth_plane, "generate_moge_artifacts") as generate:
        assert depth_plane.run(context, parameters) is generate.return_value
    generate.assert_called_once_with(context, parameters, generate_depth=True, normal_space=normal_space)
