import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pytest
from PIL import Image
from tests.anyimage.server.support import load_server_module, FakeModels


class ModelInferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moge2_model = load_server_module("models.moge")

        cls.upscale_model = load_server_module("models.upscale")

        cls.onnx_upscale = load_server_module("models.onnx_upscale")


    def test_moge2_infers_one_geometry_frame(self):
        prediction = {
            "points": np.ones((2, 2, 3), dtype=np.float32),
            "depth": np.ones((2, 2), dtype=np.float32),
            "normal": np.ones((2, 2, 3), dtype=np.float32),
            "mask": np.ones((2, 2), dtype=bool),
            "intrinsics": np.eye(3, dtype=np.float32),
        }
        with patch.object(
            self.moge2_model,
            "infer_one",
            return_value=prediction,
        ) as infer_one:
            frame = self.moge2_model.infer(
                FakeModels(),
                {"model": "MOGE2_VITS_NORMAL", "device": "cpu"},
                Path("input.png"),
                include_points=True,
            )

        self.assertEqual(frame.depth.shape, (2, 2))
        infer_one.assert_called_once()


    def test_upscale_resource_error_releases_session_and_is_readable(self):
        from PIL import Image

        class Models:
            def __init__(self, directory):
                self.model_directory = directory
                self.released = False

            def directory(self, _model):
                return self.model_directory

            def get_upscale(self, _directory, _device):
                return object()

            def release_upscale(self):
                self.released = True

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.png"
            Image.new("RGB", (8, 8)).save(path)
            models = Models(Path(directory))
            with patch.object(
                self.onnx_upscale,
                "infer",
                side_effect=self.onnx_upscale.UpscaleResourceError(
                    "provider memory exhausted"
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Reduce Maximum AI Input Size or select CPU",
                ):
                    self.upscale_model.infer_one(
                        models,
                        {
                            "model": "REALESRGAN_GENERAL_WDN_X4V3",
                            "device": "directml",
                            "max_input_size": 2048,
                        },
                        path,
                    )

            self.assertTrue(models.released)


upscale = load_server_module("models.upscale")

@pytest.mark.parametrize("key", ["REALESRGAN_GENERAL_WDN_X4V3", "HAT_GAN_X4_SHARPER", "REALESRGAN_X4PLUS"])
def test_upscale_models_resize_prediction_then_restore_alpha(tmp_path, key):
    rng = np.random.default_rng(1)
    source = Image.fromarray(rng.integers(0,256,(5,7,4),dtype=np.uint8))
    path = tmp_path / "source.png"
    source.save(path)
    prediction = Image.fromarray(rng.integers(0,256,(20,28,3),dtype=np.uint8))
    manager = SimpleNamespace(directory=lambda _: tmp_path, get_upscale=lambda *args: object())
    with patch("server.models.onnx_upscale.infer", return_value=prediction) as infer:
        output = upscale.infer_one(manager, {"model":key,"device":"cpu"}, path)
    assert infer.call_args.kwargs["tile_border"] == (48 if key == "HAT_GAN_X4_SHARPER" else 16)
    np.testing.assert_array_equal(output.convert("RGB"), prediction.resize((14,10), Image.Resampling.LANCZOS))
    np.testing.assert_array_equal(output.getchannel("A"), source.getchannel("A").resize((14,10), Image.Resampling.LANCZOS))
