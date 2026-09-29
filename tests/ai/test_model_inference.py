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


    def test_upscale_resource_error_reaches_server_job_boundary(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            from server.models.onnx_runtime import OnnxResourceError

            path = Path(directory) / "input.png"
            Image.new("RGB", (8, 8)).save(path)
            models = SimpleNamespace(get_session=lambda *_: (object(), 0.0))
            with patch.object(
                self.onnx_upscale,
                "infer",
                side_effect=OnnxResourceError(
                    "provider memory exhausted"
                ),
            ):
                with self.assertRaisesRegex(OnnxResourceError, "provider memory exhausted"):
                    self.upscale_model.infer_one(
                        models,
                        {
                            "model": "REALESRGAN_GENERAL_WDN_X4V3",
                            "device": "directml",
                            "max_input_size": 2048,
                        },
                        path,
                    )



upscale = load_server_module("models.upscale")

@pytest.mark.parametrize("key", ["REALESRGAN_GENERAL_WDN_X4V3", "HAT_GAN_X4_SHARPER", "REALESRGAN_X4PLUS"])
def test_upscale_models_resize_prediction_then_restore_alpha(tmp_path, key):
    rng = np.random.default_rng(1)
    source = Image.fromarray(rng.integers(0,256,(5,7,4),dtype=np.uint8))
    path = tmp_path / "source.png"
    source.save(path)
    prediction = Image.fromarray(rng.integers(0,256,(20,28,3),dtype=np.uint8))
    manager = SimpleNamespace(directory=lambda _: tmp_path, get_session=lambda *args: (object(), 0.0))
    with patch("server.models.onnx_upscale.infer", return_value=prediction) as infer:
        output = upscale.infer_one(manager, {"model":key,"device":"cpu"}, path)
    assert infer.call_args.kwargs["tile_border"] == (48 if key == "HAT_GAN_X4_SHARPER" else 16)
    np.testing.assert_array_equal(output.convert("RGB"), prediction.resize((14,10), Image.Resampling.LANCZOS))
    np.testing.assert_array_equal(output.getchannel("A"), source.getchannel("A").resize((14,10), Image.Resampling.LANCZOS))


def test_upscale_output_allocation_failure_clears_cache_at_job_boundary(tmp_path):
    from unittest.mock import Mock
    from server import app
    from server.models import onnx_upscale

    image_path = tmp_path / "input.png"
    Image.new("RGB", (2, 2)).save(image_path)
    manager = SimpleNamespace(get_session=lambda *_: (object(), 0.0), clear=Mock())
    context = SimpleNamespace(resource=lambda _: manager)
    parameters = {"model": "REALESRGAN_X4PLUS", "device": "cpu"}
    padded = np.zeros((256, 256, 3), dtype=np.uint8)
    with patch.object(onnx_upscale, "_pad_source", return_value=padded), patch.object(np, "empty", side_effect=MemoryError):
        with pytest.raises(RuntimeError, match="exceeded available system memory"):
            app._run_model_job(lambda ctx, args: upscale.infer_one(manager, args, image_path), context, parameters)
    manager.clear.assert_called_once_with()


def test_geometry_frame_explicitly_converts_normalized_intrinsics():
    from server.models.moge import _pixel_intrinsics

    intrinsics = np.array(((0.8, 0, 1.2), (0, 0.7, -0.1), (0, 0, 1)), np.float32)
    result = _pixel_intrinsics(intrinsics, (100, 50))
    np.testing.assert_allclose(result, ((80, 0, 120), (0, 35, -5), (0, 0, 1)), rtol=1e-6)
    assert intrinsics[0, 0] == np.float32(0.8)
