import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from PIL import Image


from server.models import onnx_ben2


class FakeSession:
    def get_providers(self):
        return ["CPUExecutionProvider"]

    def get_inputs(self):
        return [SimpleNamespace(name="input")]

    def get_outputs(self):
        return [SimpleNamespace(name="alpha")]

    def run(self, output_names, feeds):
        self.output_names = output_names
        self.feeds = feeds
        gradient = np.linspace(0.0, 1.0, 1024, dtype=np.float32)
        return [np.tile(gradient, (1024, 1))[None, None]]


class Ben2OnnxTest(unittest.TestCase):
    def test_infer_forwards_memory_release_boundary(self):
        session = FakeSession()

        with patch.object(
            onnx_ben2,
            "run_session",
            side_effect=lambda model, names, feeds, **_options: model.run(
                names, feeds
            ),
        ) as run:
            result = onnx_ben2.infer_alpha(
                session,
                Image.new("RGB", (40, 20)),
                release_memory=False,
            )

        self.assertEqual(result.shape, (20, 40))
        self.assertFalse(run.call_args.kwargs["release_memory"])

    def test_preprocess_matches_model_layout(self):
        image = Image.new("RGB", (40, 20), (64, 128, 192))
        result = onnx_ben2.preprocess(image)

        self.assertEqual(result.shape, (1, 3, 1024, 1024))
        self.assertEqual(result.dtype, np.float32)
        self.assertTrue(result.flags.c_contiguous)

    def test_infer_restores_original_size_and_alpha(self):
        session = FakeSession()
        image = Image.new("RGB", (40, 20), (10, 20, 30))

        result = onnx_ben2.infer_alpha(session, image)

        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(result.shape, (20, 40))
        self.assertEqual(session.feeds["input"].shape, (1, 3, 1024, 1024))
        self.assertLess(result[:, 0].max(), result[:, -1].min())
        self.assertTrue(np.any(np.abs(result * 255 - np.rint(result * 255)) > 0.01))

    def test_infer_rejects_nonfinite_mask(self):
        with patch.object(onnx_ben2, "run_session", return_value=[np.full((1, 1, 2, 2), np.nan)]):
            with self.assertRaisesRegex(RuntimeError, "invalid alpha"):
                onnx_ben2.infer_alpha(FakeSession(), Image.new("RGB", (2, 2)))


if __name__ == "__main__":
    unittest.main()
