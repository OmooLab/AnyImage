import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


from server.models import onnx_runtime


class FakeSession:
    def __init__(self, providers):
        self.providers = providers
        self.calls = []

    def get_providers(self):
        return self.providers

    def run(self, output_names, input_feed, run_options=None):
        self.calls.append((output_names, input_feed, run_options))
        return ["prediction"]


class OnnxRuntimeTest(unittest.TestCase):
    def test_directml_disables_parallel_execution_and_memory_pattern(self):
        options = SimpleNamespace(enable_mem_pattern=True, execution_mode="parallel")
        runtime = ModuleType("onnxruntime")
        runtime.get_available_providers = lambda: ["DmlExecutionProvider"]
        runtime.SessionOptions = lambda: options
        runtime.ExecutionMode = SimpleNamespace(ORT_SEQUENTIAL="sequential")
        calls = []
        runtime.InferenceSession = lambda path, **kwargs: calls.append(kwargs)
        with patch.dict(sys.modules, {"onnxruntime": runtime}):
            onnx_runtime.create_session("model.onnx", "directml")
        self.assertFalse(options.enable_mem_pattern)
        self.assertEqual(options.execution_mode, "sequential")
        self.assertIs(calls[0]["sess_options"], options)

    def create_runtime(self, available):
        calls = []
        runtime = ModuleType("onnxruntime")
        runtime.get_available_providers = lambda: available
        runtime.InferenceSession = lambda path, providers: calls.append(
            (path, providers)
        )
        return runtime, calls

    def test_cuda_session_uses_shrinkable_arena(self):
        runtime, calls = self.create_runtime(
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
        )

        with patch.dict(sys.modules, {"onnxruntime": runtime}):
            onnx_runtime.create_session("model.onnx", "cuda")

        self.assertEqual(
            calls[0],
            (
                "model.onnx",
                [
                    (
                        "CUDAExecutionProvider",
                        {"arena_extend_strategy": "kSameAsRequested"},
                    )
                ],
            ),
        )

    def test_coreml_and_cpu_use_plain_session_providers(self):
        runtime, calls = self.create_runtime(
            ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        )

        with patch.dict(sys.modules, {"onnxruntime": runtime}):
            onnx_runtime.create_session("model.onnx", "auto")

        self.assertEqual(
            calls[0][1],
            [
                "CoreMLExecutionProvider",
                "CPUExecutionProvider",
            ],
        )

    def test_model_options_only_configure_coreml_provider(self):
        runtime, calls = self.create_runtime(
            ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        )

        with patch.dict(sys.modules, {"onnxruntime": runtime}):
            onnx_runtime.create_session(
                "model.onnx",
                "coreml",
                coreml_options={"RequireStaticInputShapes": "1"},
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

    def test_coreml_device_selects_coreml_provider(self):
        available = [
            "CoreMLExecutionProvider",
            "CPUExecutionProvider",
        ]

        self.assertEqual(
            onnx_runtime.select_providers("coreml", available),
            ["CoreMLExecutionProvider", "CPUExecutionProvider"],
        )
        self.assertEqual(
            onnx_runtime.select_providers(
                "coreml",
                ["CPUExecutionProvider"],
            ),
            ["CPUExecutionProvider"],
        )


    def test_completing_cuda_run_shrinks_memory_arena(self):
        configs = []

        class FakeRunOptions:
            def add_run_config_entry(self, key, value):
                configs.append((key, value))

        runtime = ModuleType("onnxruntime")
        runtime.RunOptions = FakeRunOptions
        session = FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])

        with patch.dict(sys.modules, {"onnxruntime": runtime}):
            result = onnx_runtime.run_session(session, ["output"], {"input": 1})

        self.assertEqual(result, ["prediction"])
        self.assertIsInstance(session.calls[0][2], FakeRunOptions)
        self.assertEqual(
            configs,
            [("memory.enable_memory_arena_shrinkage", "gpu:0")],
        )

    def test_intermediate_and_non_cuda_runs_use_plain_session_run(self):
        cuda = FakeSession(["CUDAExecutionProvider"])
        directml = FakeSession(["DmlExecutionProvider"])

        onnx_runtime.run_session(
            cuda,
            ["output"],
            {"input": 1},
            release_memory=False,
        )
        result = onnx_runtime.run_session(
            directml,
            ["output"],
            {"input": 2},
        )

        self.assertIsNone(cuda.calls[0][2])
        self.assertIsNone(directml.calls[0][2])
        self.assertEqual(result, ["prediction"])

    def test_installed_runtime_accepts_memory_arena_shrinkage_option(self):
        import onnxruntime

        run_options = onnxruntime.RunOptions()
        run_options.add_run_config_entry(
            "memory.enable_memory_arena_shrinkage",
            "gpu:0",
        )


    def test_auto_provider_prefers_accelerated_runtime(self):
        providers = onnx_runtime.select_providers(
            "auto",
            ["CPUExecutionProvider", "DmlExecutionProvider"],
        )

        self.assertEqual(
            providers,
            ["DmlExecutionProvider", "CPUExecutionProvider"],
        )


    def test_explicit_unavailable_provider_falls_back_to_cpu(self):
        providers = onnx_runtime.select_providers(
            "cuda",
            ["CPUExecutionProvider"],
        )

        self.assertEqual(providers, ["CPUExecutionProvider"])


if __name__ == "__main__":
    unittest.main()
