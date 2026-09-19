import importlib.util
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from tests.anyimage.server.runtime_support import ServerTestCase

class GeometryArtifactsTest(ServerTestCase):
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

    def test_depth_artifacts_store_texture_and_compact_metadata(self):
        import numpy as np

        depth = importlib.import_module("server.geometry.depth_texture")
        GeometryFrame = importlib.import_module(
            "server.models.geometry"
        ).GeometryFrame
        texture_path = self.storage_root / "depth.exr"
        metadata_path = self.storage_root / "depth.json"
        validity = np.asarray(
            ((1.0, 1.0, 0.0), (1.0, 1.0, 1.0)),
            dtype=np.float32,
        )
        frame = GeometryFrame(
            depth=np.asarray(
                ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
                dtype=np.float32,
            ),
            validity=validity,
            points=np.ones((2, 3, 3), dtype=np.float32),
            intrinsics=np.eye(3, dtype=np.float32),
        )

        depth.write_depth_texture(frame, texture_path, alpha=np.ones_like(validity))
        depth.write_depth_metadata(frame, metadata_path)

        self.assertTrue(texture_path.is_file())
        self.assertEqual(texture_path.read_bytes()[:4], b"v/1\x01")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["image_size"], [3, 2])
        self.assertEqual(metadata["intrinsics"], np.eye(3).tolist())
        self.assertEqual(set(metadata), {"image_size", "intrinsics"})


    def test_object_normal_texture_matches_depth_surface_axes(self):
        import numpy as np
        from PIL import Image

        normal_texture = importlib.import_module("server.geometry.normal_texture")
        GeometryFrame = importlib.import_module(
            "server.models.geometry"
        ).GeometryFrame
        output_path = self.storage_root / "object-normal.png"
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
        frame = GeometryFrame(
            depth=np.ones((1, 4), dtype=np.float32),
            validity=np.ones((1, 4), dtype=np.float32),
            intrinsics=np.eye(3, dtype=np.float32),
            normal=camera_normals,
        )

        normal_texture.write_camera_normal_texture(
            frame,
            valid,
            (0, 0),
            (4, 1),
            (4, 1),
            output_path,
            normal_mode="OBJECT",
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


    def test_moge_model_input_preserves_rgb_independently_of_alpha(self):
        import numpy as np
        from PIL import Image

        artifacts = sys.modules["server.geometry.prediction_artifacts"]
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

        for max_size in (2048, 2):
            with self.subTest(max_size=max_size):
                outputs = []
                for source in (first_path, second_path):
                    output = artifacts._limited_model_input(
                        source, source.with_name(f"model-{source.name}"), max_size,
                    )
                    with Image.open(output) as opened:
                        self.assertEqual(opened.mode, "RGB")
                        outputs.append(np.asarray(opened))
                np.testing.assert_array_equal(*outputs)
                self.assertEqual(outputs[0].shape[1], min(3, max_size))
                if max_size == 2048:
                    np.testing.assert_array_equal(outputs[0], first[..., :3])


    def test_moge_artifact_orchestration_uses_one_geometry_frame(self):
        import numpy as np
        from PIL import Image

        artifacts = sys.modules["server.geometry.prediction_artifacts"]
        GeometryFrame = importlib.import_module(
            "server.models.geometry"
        ).GeometryFrame
        input_path = self.storage_root / "selection.png"
        source = Image.new("RGBA", (4, 4), (255, 128, 64, 255))
        source.paste((255, 128, 64, 0), (2, 0, 4, 2))
        source.save(input_path)
        output_directory = self.storage_root / "job"
        output_directory.mkdir()
        context = SimpleNamespace(
            directory=output_directory,
            resource=lambda _name: object(),
            progress=lambda *_args: None,
            check_cancelled=lambda: None,
        )
        frame = GeometryFrame(
            depth=np.ones((2, 2), dtype=np.float32),
            validity=np.ones((2, 2), dtype=np.float32),
            intrinsics=np.eye(3, dtype=np.float32),
            normal=np.zeros((2, 2, 3), dtype=np.float32),
            points=np.ones((2, 2, 3), dtype=np.float32),
        )

        texture = importlib.import_module("server.geometry.depth_texture")
        with (
            patch.object(artifacts.moge, "infer", return_value=frame) as infer,
            patch.object(texture, "write_float_exr", wraps=texture.write_float_exr) as write,
        ):
            result = artifacts.generate_moge_artifacts(
                context,
                {"max_input_size": 2048},
                input_path,
                generate_depth=True,
                normal_mode="OBJECT",
            )

        np.testing.assert_array_equal(write.call_args.args[0][..., 3], [[1, 0], [1, 1]])
        np.testing.assert_array_equal(frame.validity, np.ones((2, 2)))
        metadata = json.loads(result["depth_metadata"].read_text())
        self.assertEqual(metadata["image_size"], [2, 2])
        self.assertNotIn("reference_depth", metadata)
        infer.assert_called_once()
        self.assertEqual(
            set(result),
            {"depth", "depth_metadata", "object_normal"},
        )
        self.assertFalse((output_directory / "model-input.png").exists())
        self.assertTrue(all(path.is_file() for path in result.values()))
        self.assertTrue(infer.call_args.kwargs["include_points"])


    def test_generate_cutout_artifacts_only_returns_requested_outputs(self):
        job = sys.modules["server.jobs.cutout"]
        input_path = self.storage_root / "input.png"
        input_path.write_bytes(b"selection")
        context = SimpleNamespace(
            directory=self.storage_root / "job",
            progress=lambda *_args: None,
            check_cancelled=lambda: None,
        )
        depth_texture = context.directory / "depth.exr"
        metadata = context.directory / "depth.json"
        normal = context.directory / "object-normal.png"
        with patch.object(
            job,
            "generate_moge_artifacts",
            return_value={
                "depth": depth_texture,
                "depth_metadata": metadata,
                "object_normal": normal,
            },
        ) as generate:
            result = job.run(
                context,
                {
                    "input": str(input_path),
                    "generate_depth": True,
                    "normal_mode": "OBJECT",
                },
            )

        self.assertEqual(
            result,
            {
                "depth": "depth.exr",
                "depth_metadata": "depth.json",
                "object_normal": "object-normal.png",
            },
        )
        generate.assert_called_once_with(
            context,
            {
                "input": str(input_path),
                "generate_depth": True,
                "normal_mode": "OBJECT",
            },
            input_path,
            generate_depth=True,
            normal_mode="OBJECT",
        )
