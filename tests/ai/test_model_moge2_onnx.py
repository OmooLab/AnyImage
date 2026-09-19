from tests.support.paths import PROJECT_ROOT
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
import numpy as np


def load_module():
    anyimage = ModuleType("anyimage")
    anyimage.__path__ = [str(PROJECT_ROOT / "src" / "anyimage")]
    server = ModuleType("anyimage.server")
    server.__path__ = [str(PROJECT_ROOT / "src" / "anyimage" / "server")]
    models = ModuleType("anyimage.server.models")
    models.__path__ = [
        str(PROJECT_ROOT / "src" / "anyimage" / "server" / "models")
    ]
    specification = importlib.util.spec_from_file_location(
        "anyimage.server.models.onnx_moge2",
        PROJECT_ROOT
        / "src"
        / "anyimage"
        / "server"
        / "models"
        / "onnx_moge2.py",
    )
    module = importlib.util.module_from_spec(specification)
    with patch.dict(
        sys.modules,
        {
            "anyimage": anyimage,
            "anyimage.server": server,
            "anyimage.server.models": models,
        },
    ):
        specification.loader.exec_module(module)
    return module


class FakeInput:
    def __init__(self, name):
        self.name = name


class FakeSession:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def run(self, names, inputs):
        self.calls.append((names, inputs))
        return [self.outputs[name] for name in names]

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def get_outputs(self):
        return [FakeInput(name) for name in self.outputs]


class Moge2OnnxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.moge = load_module()


    def test_coreml_session_requires_static_input_partitions(self):
        calls = []
        fake_runtime = ModuleType("onnxruntime")
        fake_runtime.get_available_providers = lambda: [
            "CoreMLExecutionProvider",
            "CPUExecutionProvider",
        ]
        fake_runtime.InferenceSession = lambda path, providers: calls.append(
            (path, providers)
        )

        with patch.dict(sys.modules, {"onnxruntime": fake_runtime}):
            self.moge.create_session("moge-model", "coreml")

        self.assertEqual(
            calls[0][0],
            str(Path("moge-model") / "model.onnx"),
        )
        self.assertEqual(
            calls[0][1],
            [
                (
                    "CoreMLExecutionProvider",
                    {"RequireStaticInputShapes": "1"},
                ),
                "CPUExecutionProvider",
            ],
        )


    def test_infer_uses_dynamic_token_input_and_numpy_postprocess(self):
        height, width = 8, 12
        raw = {
            "points": np.zeros((1, height, width, 3), dtype=np.float32),
            "normal": np.zeros((1, height, width, 3), dtype=np.float32),
            "mask": np.ones((1, height, width), dtype=np.float32),
            "scale": np.ones((1,), dtype=np.float32),
        }
        raw["points"][..., 2] = 1.0
        raw["normal"][..., 2] = 1.0
        session = FakeSession(raw)
        expected = {
            "points": np.zeros((height, width, 3), dtype=np.float32),
            "depth": np.ones((height, width), dtype=np.float32),
            "normal": raw["normal"][0],
            "mask": np.ones((height, width), dtype=bool),
            "intrinsics": np.eye(3, dtype=np.float32),
        }

        with patch.object(self.moge, "postprocess", return_value=expected):
            result = self.moge.infer(
                session,
                np.zeros((height, width, 3), dtype=np.float32),
                resolution_level=9,
            )

        self.assertIs(result, expected)
        names, inputs = session.calls[0]
        self.assertEqual(names, ["points", "normal", "mask", "scale"])
        self.assertEqual(inputs["image"].shape, (1, 3, height, width))
        self.assertEqual(inputs["num_tokens"].dtype, np.int64)
        self.assertEqual(inputs["num_tokens"], 3600)

    def test_infer_forwards_memory_release_boundary(self):
        height, width = 8, 12
        raw = {
            "points": np.zeros((1, height, width, 3), dtype=np.float32),
            "normal": np.zeros((1, height, width, 3), dtype=np.float32),
            "mask": np.ones((1, height, width), dtype=np.float32),
            "scale": np.ones((1,), dtype=np.float32),
        }
        session = FakeSession(raw)

        with (
            patch.object(self.moge, "postprocess", return_value={}),
            patch.object(
                self.moge,
                "run_session",
                side_effect=lambda model, names, feeds, **_options: model.run(
                    names, feeds
                ),
            ) as run,
        ):
            self.moge.infer(
                session,
                np.zeros((height, width, 3), dtype=np.float32),
                0,
                release_memory=False,
            )

        self.assertFalse(run.call_args.kwargs["release_memory"])

    def test_postprocess_recovers_camera_projection_and_metric_scale(self):
        height, width = 64, 80
        focal = np.float32(0.9)
        shift = np.float32(0.3)
        metric_scale = np.float32(2.0)
        uv = self.moge.normalized_view_plane_uv(width, height, np.float32)
        depth = np.linspace(1.0, 2.4, height * width, dtype=np.float32).reshape(
            height,
            width,
        )
        raw_points = np.concatenate(
            (uv * depth[..., None] / focal, (depth - shift)[..., None]),
            axis=-1,
        )
        raw = {
            "points": raw_points[None],
            "normal": np.broadcast_to(
                np.array((0.0, 0.0, 1.0), dtype=np.float32),
                (1, height, width, 3),
            ),
            "mask": np.ones((1, height, width), dtype=np.float32),
            "metric_scale": np.array((metric_scale,), dtype=np.float32),
        }

        raw["mask"][0, 0, :4] = [0.0, 0.2, 0.7, 1.0]
        result = self.moge.postprocess(raw)

        np.testing.assert_allclose(result["depth"], depth * metric_scale, rtol=1e-3)
        np.testing.assert_allclose(result["points"][..., 2], result["depth"], rtol=1e-5)
        np.testing.assert_array_equal(result["mask"], raw["mask"][0])

    def test_postprocess_preserves_mask_for_nonpositive_depth(self):
        mask = np.array([[[0.2, 0.7], [0.0, 1.0]]], dtype=np.float32)
        raw = {
            "points": np.zeros((1, 2, 2, 3), dtype=np.float32),
            "normal": np.zeros((1, 2, 2, 3), dtype=np.float32),
            "mask": mask,
            "metric_scale": np.ones(1, dtype=np.float32),
        }
        with patch.object(self.moge, "recover_focal_shift", return_value=(1.0, -1.0)) as recover:
            result = self.moge.postprocess(raw)
        np.testing.assert_array_equal(recover.call_args.args[1], mask[0] > 0.5)
        np.testing.assert_array_equal(result["mask"], mask[0])
        self.assertTrue((result["depth"] < 0).all())


if __name__ == "__main__":
    unittest.main()
