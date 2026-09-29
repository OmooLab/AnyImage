import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import numpy as np


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
        from server.models import onnx_moge2
        cls.moge = onnx_moge2


    def test_coreml_session_requires_static_input_partitions(self):
        calls = []
        fake_runtime = ModuleType("onnxruntime")
        fake_runtime.get_available_providers = lambda: [
            "CoreMLExecutionProvider",
            "CPUExecutionProvider",
        ]
        def create(path, providers, **kwargs):
            calls.append((path, providers))
            return SimpleNamespace(get_providers=lambda: ["CoreMLExecutionProvider", "CPUExecutionProvider"])
        fake_runtime.InferenceSession = create

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



if __name__ == "__main__":
    unittest.main()
