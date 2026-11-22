import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tests.anyimage.server.support import load_server_module, FakeJobContext


class ServerJobsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resolution = load_server_module("media.resolution")

        cls.background = load_server_module("jobs.remove_background")

        cls.depth_plane_job = load_server_module("jobs.depth_plane")


    def test_plane_job_requests_matching_normal_space(self):
        for plane_type in ("DEPTH", "RELIEF"):
            normal_space = "OBJECT" if plane_type == "DEPTH" else "TANGENT"
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                context = FakeJobContext(root / "result", "generate_depth_plane_geometry")
                parameters = {"input": str(root / "input.png"), "plane_type": plane_type}
                with patch.object(self.depth_plane_job, "generate_moge_artifacts") as generate:
                    self.assertIs(self.depth_plane_job.run(context, parameters), generate.return_value)
            generate.assert_called_once_with(
                context,
                parameters,
                generate_depth=True,
                normal_space=normal_space,
            )


    def test_ben2_preserves_input_alpha_and_hides_transparent_rgb(self):
        from PIL import Image

        onnx_ben2 = load_server_module("models.onnx_ben2")
        source_pixels = np.asarray(
            (((255, 0, 0, 0), (0, 255, 0, 128)),),
            dtype=np.uint8,
        )
        model_result = np.full((1, 2), 128 / 255, np.float32)
        received = []

        def infer(_model, image, **_options):
            received.append(np.asarray(image.convert("RGB"), dtype=np.uint8))
            return model_result

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.png"
            Image.fromarray(source_pixels, mode="RGBA").save(input_path)
            with (
                patch.object(onnx_ben2, "infer_alpha", side_effect=infer),
            ):
                context = FakeJobContext(Path(directory) / "job", "remove_background")
                result = self.background.run(context, {
                    "input": str(input_path), "model": "BEN2_BASE", "device": "cpu",
                })
            np.testing.assert_array_equal(np.load(context.directory / result["alpha"]), model_result)

        inference_pixels = received[0]
        self.assertEqual(tuple(inference_pixels[0, 0]), (0, 0, 0))
        self.assertEqual(tuple(inference_pixels[0, 1]), (0, 128, 0))


    def test_background_alpha_job_preserves_float_precision(self):
        from PIL import Image
        onnx_ben2 = load_server_module("models.onnx_ben2")
        alpha = np.array([[0.123456, 0.987654]], dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.png"
            Image.new("RGB", (2, 1)).save(path)
            context = FakeJobContext(root / "result", "remove_background")
            with (
                patch.object(onnx_ben2, "infer_alpha", return_value=alpha),
            ):
                result = self.background.run(context, {"input": str(path), "model": "BEN2_BASE", "device": "cpu"})
            self.assertEqual(result, {"alpha": "alpha.npy"})
            np.testing.assert_array_equal(np.load(context.directory / result["alpha"], allow_pickle=False), alpha)
            self.assertFalse(list(context.directory.glob("*.png")))


    def test_upscale_input_uses_the_global_long_edge_limit(self):
        from PIL import Image

        source = Image.new("RGB", (3000, 1500))
        limited = self.resolution.limit_image(source, 2048)

        self.assertEqual(limited.size, (2048, 1024))
        self.assertEqual(
            self.resolution.limit_image(Image.new("RGB", (800, 600)), 2048).size,
            (800, 600),
        )
        with self.assertRaisesRegex(ValueError, "between 1 and 8192"):
            self.resolution.limit_image(source, 9000)
