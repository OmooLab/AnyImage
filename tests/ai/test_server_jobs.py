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

        cls.background_model = load_server_module("models.background")

        cls.onnx_upscale = load_server_module("models.onnx_upscale")

        cls.depth_plane_job = load_server_module("jobs.depth_plane")

        cls.upscale_job = load_server_module("jobs.upscale")


    def test_plane_job_requests_depth_and_matching_normal_space(self):
        for plane_type, normal_space in (("DEPTH", "OBJECT"), ("RELIEF", "TANGENT")):
            normal_key = f"{normal_space.lower()}_normal"
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_path = root / "input.png"
                input_path.touch()
                context = FakeJobContext(root / "result", "generate-depth-plane-geometry")
                depth_texture = context.directory / "depth.exr"
                metadata = context.directory / "depth.json"
                normal_texture = context.directory / f"{normal_space.lower()}-normal.png"
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
                    normal_key: f"{normal_space.lower()}-normal.png",
                },
            )
            generate.assert_called_once_with(
                context,
                parameters,
                input_path,
                generate_depth=True,
                normal_mode=normal_space,
            )


    def test_ben2_background_removal_writes_fast_transparent_png(self):
        from PIL import Image
        onnx_ben2 = load_server_module("models.onnx_ben2")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.png"
            Image.new("RGBA", (2, 1), (255, 64, 32, 128)).save(input_path)
            context = FakeJobContext(root / "result", "remove-background")
            with (
                patch.object(onnx_ben2, "create_session", return_value=object()),
                patch.object(onnx_ben2, "infer_alpha", return_value=np.full((1, 2), 128 / 255, np.float32)) as infer,
                patch.object(Image.Image, "save", autospec=True, side_effect=Image.Image.save) as save,
            ):
                result = self.background.run(context, {"input": str(input_path), "model": "BEN2_BASE", "device": "cpu"})
            self.assertEqual(result, {"foreground": "foreground.png"})
            self.assertEqual([p.name for p in context.directory.glob("*.png")], ["foreground.png"])
            with Image.open(root / "result" / "foreground.png") as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 64, 32, 64))
            self.assertEqual(infer.call_args.kwargs, {"release_memory": True})
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
                patch.object(onnx_ben2, "create_session", return_value=object()),
                patch.object(onnx_ben2, "infer_alpha", side_effect=infer),
            ):
                result, _load_ms, _inference_ms = self.background_model.infer_foreground(
                    input_path,
                    "BEN2-ONNX",
                    "cpu",
                    preserve_input_alpha=True,
                )
                raw_result, _load_ms, _inference_ms = self.background_model.infer_foreground(
                    input_path,
                    "BEN2-ONNX",
                    "cpu",
                )

        inference_pixels = received[0]
        result_pixels = np.asarray(result.convert("RGBA"), dtype=np.uint8)
        self.assertEqual(tuple(inference_pixels[0, 0]), (0, 0, 0))
        self.assertEqual(tuple(inference_pixels[0, 1]), (0, 128, 0))
        self.assertEqual(tuple(received[1][0, 0]), (0, 0, 0))
        self.assertEqual(tuple(received[1][0, 1]), (0, 128, 0))
        self.assertEqual(tuple(result_pixels[0, 0]), (255, 0, 0, 0))
        self.assertEqual(tuple(result_pixels[0, 1]), (0, 255, 0, 64))
        self.assertEqual(
            tuple(np.asarray(raw_result.convert("RGBA"))[0, 0]),
            (0, 0, 0, 128),
        )


    def test_background_alpha_job_preserves_float_precision(self):
        from PIL import Image
        onnx_ben2 = load_server_module("models.onnx_ben2")
        alpha = np.array([[0.123456, 0.987654]], dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.png"
            Image.new("RGB", (2, 1)).save(path)
            context = FakeJobContext(root / "result", "remove-background")
            with (
                patch.object(onnx_ben2, "create_session", return_value=object()),
                patch.object(onnx_ben2, "infer_alpha", return_value=alpha),
            ):
                result = self.background.run(context, {"input": str(path), "model": "BEN2_BASE", "device": "cpu", "output_kind": "alpha"})
            self.assertEqual(result, {"alpha": "alpha.npy"})
            np.testing.assert_array_equal(np.load(context.directory / result["alpha"], allow_pickle=False), alpha)
            self.assertFalse(list(context.directory.glob("*.png")))


    def test_upscale_job_returns_one_image_file(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.png"
            input_path.touch()
            context = FakeJobContext(root / "result", "upscale-image")
            with patch.object(
                self.upscale_job,
                "infer_one",
                return_value=Image.new("RGB", (8, 8), (10, 20, 30)),
            ) as infer_one:
                result = self.upscale_job.run(
                    context,
                    {
                        "input": str(input_path),
                        "model": "REALESRGAN_GENERAL_WDN_X4V3",

                        "device": "cpu",
                    },
                )

            self.assertEqual(infer_one.call_count, 1)
            self.assertEqual(result, {"upscale": "upscale.png"})
            colors = sorted(context.directory.glob("*.png"))
            self.assertEqual(
                [path.name for path in colors],
                ["upscale.png"],
            )
            self.assertIn(
                (
                    "INFO",
                    "Upscale model: REALESRGAN_GENERAL_WDN_X4V3; "
                    "maximum AI input size: 2048 px",
                ),
                context.logs,
            )


    def test_upscale_job_preserves_source_alpha(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.png"
            pixels = np.zeros((3, 5, 4), dtype=np.uint8)
            pixels[..., :3] = (10, 20, 30)
            pixels[..., 3] = np.arange(5, dtype=np.uint8) * 60
            Image.fromarray(pixels, mode="RGBA").save(source_path)
            context = FakeJobContext(root / "result", "upscale-image")
            prediction = Image.new("RGB", (20, 12), (10, 20, 30))

            with patch.object(
                self.onnx_upscale,
                "infer",
                return_value=prediction,
            ):
                self.upscale_job.run(
                    context,
                    {
                        "input": str(source_path),
                        "model": "REALESRGAN_GENERAL_WDN_X4V3",

                        "device": "cpu",
                    },
                )

            with Image.open(context.directory / "upscale.png") as result:
                self.assertEqual(result.mode, "RGBA")
                self.assertEqual(result.size, (10, 6))
                alpha = np.asarray(result.getchannel("A"))
                expected_alpha = np.asarray(
                    Image.fromarray(pixels[:, :, 3], mode="L").resize(
                        result.size,
                        Image.Resampling.LANCZOS,
                    )
                )
                np.testing.assert_array_equal(alpha, expected_alpha)
                self.assertLess(
                    int(alpha[:, 0].max()),
                    int(alpha[:, -1].min()),
                )


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
