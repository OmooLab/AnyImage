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
            normal_key = f"{normal_space.lower()}_normal"
            normal_filename = f"{normal_space.lower()}-normal.png"
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_path = root / "input.png"
                input_path.touch()
                context = FakeJobContext(root / "result", "generate_depth_plane_geometry")
                depth_texture = context.directory / "depth.exr"
                metadata = context.directory / "depth.json"
                normal_texture = context.directory / normal_filename
                parameters = {"input": str(input_path), "plane_type": plane_type}
                with (
                    patch.object(
                        self.depth_plane_job,
                        "validate_input_path",
                        return_value=input_path,
                    ),
                    patch.object(
                        self.depth_plane_job,
                        "generate_moge_artifacts",
                        return_value={
                            "depth": depth_texture,
                            "depth_metadata": metadata,
                            normal_key: normal_texture,
                        },
                    ) as generate,
                ):
                    result = self.depth_plane_job.run(context, parameters)

            self.assertEqual(
                result,
                {
                    "depth": "depth.exr",
                    "depth_metadata": "depth.json",
                    normal_key: normal_filename,
                },
            )
            generate.assert_called_once_with(
                context,
                parameters,
                input_path,
                generate_depth=True,
                generate_normal=True,
                normal_space=normal_space,
            )


    def test_ben2_background_removal_writes_fast_transparent_png(self):
        from PIL import Image
        onnx_ben2 = load_server_module("models.onnx_ben2")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.png"
            Image.new("RGBA", (2, 1), (255, 64, 32, 128)).save(input_path)
            context = FakeJobContext(root / "result", "remove_background")
            with (
                patch.object(onnx_ben2, "infer_alpha", return_value=np.full((1, 2), 128 / 255, np.float32)) as infer,
                patch.object(Image.Image, "save", autospec=True, side_effect=Image.Image.save) as save,
            ):
                result = self.background.run(context, {"input": str(input_path), "model": "BEN2_BASE", "device": "cpu"})
            self.assertEqual(result, {"foreground": "foreground.png"})
            self.assertEqual([p.name for p in context.directory.glob("*.png")], ["foreground.png"])
            with Image.open(root / "result" / "foreground.png") as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 64, 32, 64))
            self.assertEqual(save.call_args.kwargs, {"format": "PNG", "compress_level": 1})
        self.assertIn("Background removed in", context.status["message"])


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
            with Image.open(context.directory / result["foreground"]) as output:
                result_pixels = np.asarray(output, dtype=np.uint8)

        inference_pixels = received[0]
        self.assertEqual(tuple(inference_pixels[0, 0]), (0, 0, 0))
        self.assertEqual(tuple(inference_pixels[0, 1]), (0, 128, 0))
        self.assertEqual(tuple(result_pixels[0, 0]), (255, 0, 0, 0))
        self.assertEqual(tuple(result_pixels[0, 1]), (0, 255, 0, 64))


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
                result = self.background.run(context, {"input": str(path), "model": "BEN2_BASE", "device": "cpu", "output_kind": "alpha"})
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
