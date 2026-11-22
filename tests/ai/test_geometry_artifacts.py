import importlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.anyimage.server.support import FakeJobContext


class GeometryArtifactsTest(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.storage_root = Path(directory)

    def test_depth_alpha_multiplies_coverage_without_changing_geometry(self):
        import numpy as np

        depth = importlib.import_module("server.geometry.depth_texture")
        GeometryFrame = importlib.import_module("server.models.geometry").GeometryFrame
        validity = np.asarray([[0.75, 0, 1, 1]], dtype=np.float32)
        alpha = np.asarray([[0.8, 1, 0, 1]], dtype=np.float32)
        points = np.arange(12, dtype=np.float32).reshape(1, 4, 3)
        frame = GeometryFrame(
            depth=points[..., 2], points=points,
            validity=validity.copy(), intrinsics=np.eye(3, dtype=np.float32),
        )
        output = self.storage_root / "depth.exr"
        with patch.object(depth, "write_float_exr") as write:
            depth.write_depth_texture(frame, output, alpha=alpha)
            packed = write.call_args.args[0]
            np.testing.assert_allclose(packed[..., 3], [[0.6, 0, 0, 1]])
            np.testing.assert_array_equal(packed[..., :3], points)
            np.testing.assert_array_equal(frame.validity, validity)
            self.assertEqual(packed.dtype, np.float32)
            with self.assertRaisesRegex(ValueError, "Alpha.*dimensions"):
                depth.write_depth_texture(frame, output, alpha=np.ones((4, 1)))
            self.assertEqual(write.call_count, 1)

    def test_normal_texture_matches_tangent_and_object_axes(self):
        import numpy as np
        from PIL import Image

        normal_texture = importlib.import_module("server.geometry.normal_texture")
        output_path = self.storage_root / "tangent-normal.png"
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
        normal_texture.write_normal_texture(
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


        normal_texture.write_normal_texture(
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


    def test_moge_model_input_preserves_rgb_independently_of_alpha(self):
        import numpy as np
        from PIL import Image

        artifacts = importlib.import_module("server.geometry.prediction_artifacts")
        first_path = self.storage_root / "first.png"
        second_path = self.storage_root / "second.png"
        first = np.asarray(
            [[(240, 120, 60, 0), (200, 100, 50, 128), (9, 8, 7, 255)]],
            dtype=np.uint8,
        )
        second = first.copy()
        second[..., 3] = 255
        Image.fromarray(first, mode="RGBA").save(first_path)
        Image.fromarray(second, mode="RGBA").save(second_path)
        context = FakeJobContext(self.storage_root, "generate_cutout_artifacts")
        moge = importlib.import_module("server.models.onnx_moge2")
        parameters = {"model": "MOGE2_VITS_NORMAL", "device": "cpu", "resolution_level": 0}

        for max_size in (2048, 2):
            with self.subTest(max_size=max_size):
                outputs = []
                for source in (first_path, second_path):
                    with (
                        patch.object(moge, "infer_normal", side_effect=lambda session, rgb, level: rgb) as infer,
                        patch.object(artifacts, "write_normal_texture"),
                    ):
                        artifacts.generate_moge_artifacts(
                            context, {**parameters, "input": str(source), "max_input_size": max_size}, generate_depth=False,
                        )
                    outputs.append(infer.call_args.args[1])
                np.testing.assert_array_equal(*outputs)
                self.assertEqual(outputs[0].shape[1], min(3, max_size))
                if max_size == 2048:
                    np.testing.assert_allclose(outputs[0], first[..., :3] / 255)


    def test_moge_artifact_orchestration_uses_one_geometry_frame(self):
        import numpy as np
        from PIL import Image

        artifacts = importlib.import_module("server.geometry.prediction_artifacts")
        GeometryFrame = importlib.import_module(
            "server.models.geometry"
        ).GeometryFrame
        input_path = self.storage_root / "selection.png"
        source = Image.new("RGBA", (4, 4), (255, 128, 64, 255))
        source.paste((255, 128, 64, 0), (2, 0, 4, 2))
        source.save(input_path)
        output_directory = self.storage_root / "job"
        output_directory.mkdir()
        context = FakeJobContext(output_directory, "generate_depth_plane_geometry")
        frame = GeometryFrame(
            depth=np.ones((2, 2), dtype=np.float32),
            validity=np.ones((2, 2), dtype=np.float32),
            intrinsics=np.eye(3, dtype=np.float32),
            normal=np.zeros((2, 2, 3), dtype=np.float32),
            points=np.ones((2, 2, 3), dtype=np.float32),
        )

        texture = importlib.import_module("server.geometry.depth_texture")
        with (
            patch.object(artifacts, "infer_geometry", return_value=frame) as infer,
            patch.object(texture, "write_float_exr", wraps=texture.write_float_exr) as write,
        ):
            result = artifacts.generate_moge_artifacts(
                context,
                {"input": str(input_path), "model": "MOGE2_VITS_NORMAL", "resolution_level": 1, "device": "cpu"},
                generate_depth=True,
            )

        np.testing.assert_array_equal(write.call_args.args[0][..., 3], [[1, 0], [1, 1]])
        np.testing.assert_array_equal(frame.validity, np.ones((2, 2)))
        self.assertEqual(result, {"depth": "depth.exr", "intrinsics": frame.intrinsics.tolist(),
                                  "tangent_normal": "tangent-normal.png"})
        self.assertEqual({path.name for path in output_directory.iterdir()}, {"depth.exr", "tangent-normal.png"})
        infer.assert_called_once()


    def test_generate_cutout_artifacts_only_returns_requested_outputs(self):
        job = importlib.import_module("server.jobs.cutout")
        input_path = self.storage_root / "input.png"
        context = SimpleNamespace(
            directory=self.storage_root / "job",
            progress=lambda *_args: None,
            check_cancelled=lambda: None,
        )
        parameters = {"input": str(input_path), "generate_depth": True}
        with patch.object(job, "generate_moge_artifacts") as generate:
            self.assertIs(job.run(context, parameters), generate.return_value)

        generate.assert_called_once_with(
            context,
            {
                "input": str(input_path),
                "generate_depth": True,
            },
            generate_depth=True,
            normal_space="OBJECT",
        )
