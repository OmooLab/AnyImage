import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image


from server.models import onnx_upscale


class FakeSession:
    def get_providers(self):
        return ["CPUExecutionProvider"]

    def get_inputs(self):
        return [SimpleNamespace(name="input")]

    def get_outputs(self):
        return [SimpleNamespace(name="output")]

    def run(self, output_names, feeds):
        self.output_names = output_names
        self.feeds = feeds
        source = feeds["input"]
        return [np.repeat(np.repeat(source, 4, axis=2), 4, axis=3)]


class UpscaleOnnxTest(unittest.TestCase):
    def test_wider_context_preserves_pixels_across_odd_and_small_images(self):
        for width, height in [(1, 1), (7, 5), (321, 163)]:
            pixels = np.random.default_rng(7).integers(0, 256, (height, width, 3), dtype=np.uint8)
            result = onnx_upscale.infer(FakeSession(), Image.fromarray(pixels), tile_border=48)
            expected = np.repeat(np.repeat(pixels, 4, axis=0), 4, axis=1)
            np.testing.assert_array_equal(np.asarray(result), expected)


    def test_preprocess_matches_dynamic_rgb_layout(self):
        image = Image.new("RGB", (7, 5), (64, 128, 192))

        result = onnx_upscale.preprocess(image)

        self.assertEqual(result.shape, (1, 3, 5, 7))
        self.assertEqual(result.dtype, np.float32)
        self.assertTrue(result.flags.c_contiguous)
        np.testing.assert_allclose(
            result[0, :, 0, 0],
            np.array((64, 128, 192), dtype=np.float32) / 255.0,
        )

    def test_infer_returns_direct_four_x_rgb_prediction(self):
        session = FakeSession()
        image = Image.new("RGB", (7, 5), (10, 20, 30))

        result = onnx_upscale.infer(session, image)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (28, 20))
        self.assertEqual(session.output_names, ["output"])
        self.assertEqual(session.feeds["input"].shape, (1, 3, 256, 256))
        self.assertEqual(result.getpixel((0, 0)), (10, 20, 30))

    def test_infer_returns_raw_rgb_for_rgba_input(self):
        session = FakeSession()
        pixels = np.zeros((5, 7, 4), dtype=np.uint8)
        pixels[..., :3] = (10, 20, 30)
        pixels[..., 3] = np.arange(7, dtype=np.uint8) * 40
        image = Image.fromarray(pixels, mode="RGBA")

        result = onnx_upscale.infer(session, image)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (28, 20))
        self.assertEqual(result.getpixel((0, 0)), (10, 20, 30))

    def test_tiles_use_reflected_context_at_outer_image_edges(self):
        class RecordingSession(FakeSession):
            def run(self, output_names, feeds):
                self.input = feeds["input"].copy()
                return super().run(output_names, feeds)

        pixels = np.zeros((5, 7, 3), dtype=np.uint8)
        pixels[..., 0] = np.arange(7, dtype=np.uint8) * 20
        session = RecordingSession()

        onnx_upscale.infer(
            session,
            Image.fromarray(pixels, mode="RGB"),
        )

        red = session.input[0, 0]
        self.assertAlmostEqual(red[16, 22], 120 / 255.0)
        self.assertAlmostEqual(red[16, 23], 100 / 255.0)


    def test_all_models_split_large_inputs_into_fixed_tiles(self):
        class CountingSession(FakeSession):
            def __init__(self):
                self.calls = 0

            def run(self, output_names, feeds):
                self.calls += 1
                return super().run(output_names, feeds)

        session = CountingSession()
        result = onnx_upscale.infer(
            session,
            Image.new("RGB", (449, 225), (1, 2, 3)),
        )

        self.assertEqual(result.size, (1796, 900))
        self.assertEqual(session.calls, 6)
        self.assertEqual(session.feeds["input"].shape, (1, 3, 256, 256))

    def test_only_final_tile_releases_memory(self):
        releases = []
        session = FakeSession()

        def run(model, output_names, feeds, *, release_memory):
            releases.append(release_memory)
            return model.run(output_names, feeds)

        with patch.object(onnx_upscale, "run_session", side_effect=run):
            result = onnx_upscale.infer(
                session,
                Image.new("RGB", (449, 225), (1, 2, 3)),
            )

        self.assertEqual(result.size, (1796, 900))
        self.assertEqual(releases, [False, False, False, False, False, True])

    def test_non_final_image_does_not_release_its_final_tile(self):
        releases = []
        session = FakeSession()

        def run(model, output_names, feeds, *, release_memory):
            releases.append(release_memory)
            return model.run(output_names, feeds)

        with patch.object(onnx_upscale, "run_session", side_effect=run):
            onnx_upscale.infer(
                session,
                Image.new("RGB", (449, 225), (1, 2, 3)),
                release_memory=False,
            )

        self.assertEqual(releases, [False] * 6)

    def test_provider_unicode_error_is_presented_as_resource_error(self):
        class InvalidProviderSession(FakeSession):
            def run(self, _output_names, _feeds):
                raise UnicodeDecodeError("utf-8", b"\xc4", 0, 1, "invalid")

        with self.assertRaisesRegex(
            onnx_upscale.UpscaleResourceError,
            "provider failed",
        ):
            onnx_upscale.infer(
                InvalidProviderSession(),
                Image.new("RGB", (7, 5)),
            )


if __name__ == "__main__":
    unittest.main()
