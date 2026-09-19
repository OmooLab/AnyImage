import importlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class AiSetupTest(BlenderTestCase):
    def test_anyimage_post_install_is_ordinary_code_using_runtime_request(self):
        calls = []
        fake_runtime = SimpleNamespace(
            request=lambda job_type, parameters: calls.append((job_type, parameters))
        )
        self.runtime.post_install(fake_runtime)
        self.assertEqual(
            calls,
            [
                ("download-model", {"model": "MOGE2_VITS_NORMAL"}),
                ("download-model", {"model": "BIREFNET_LITE"}),
                (
                    "download-model",
                    {"model": "REALESRGAN_GENERAL_WDN_X4V3"},
                ),
            ],
        )


    def test_anyimage_post_install_names_each_failed_model(self):
        calls = []

        def request(_job_type, parameters):
            calls.append(parameters["model"])
            raise RuntimeError("network unavailable")

        with self.assertRaisesRegex(
            RuntimeError,
            (
                "MoGe-2 ViT-S Normal: network unavailable; "
                "BiRefNet Lite: network unavailable; "
                "Real-ESRGAN General WDN x4v3: network unavailable"
            ),
        ):
            self.runtime.post_install(SimpleNamespace(request=request))

        self.assertEqual(
            calls,
            [
                "MOGE2_VITS_NORMAL",
                "BIREFNET_LITE",
                "REALESRGAN_GENERAL_WDN_X4V3",
            ],
        )


    def test_required_model_operator_requests_all_default_models(self):
        operator = self.anyimage.operators.DownloadRequiredModels()
        with patch.object(self.ai_setup, "require_environment"):
            parameters = operator.request(None)

        self.assertEqual(
            parameters,
            {
                "models": [
                    "MOGE2_VITS_NORMAL",
                    "BIREFNET_LITE",
                    "REALESRGAN_GENERAL_WDN_X4V3",
                ]
            },
        )


    def test_ai_status_checks_environment_and_required_model_files(self):
        properties = self.anyimage.properties
        with (
            patch.object(self.anyimage.runtime, "environment_ready", return_value=True),
            patch.object(
                properties,
                "model_catalog",
                return_value=(
                    {"key": "MOGE2_VITS_NORMAL", "ready": True},
                    {"key": "BIREFNET_LITE", "ready": False},
                    {
                        "key": "REALESRGAN_GENERAL_WDN_X4V3",
                        "ready": True,
                    },
                ),
            ),
        ):
            status = properties.ai_status()
        self.assertTrue(status["environment_ready"])
        self.assertEqual(status["missing_models"], ("BIREFNET_LITE",))
        self.assertFalse(status["ready"])
        self.assertEqual(properties.ai_setup_label(status), "Download Required Models…")

        with (
            patch.object(self.anyimage.runtime, "environment_ready", return_value=False),
            patch.object(
                properties,
                "model_catalog",
                return_value=tuple(
                    {"key": key, "ready": True}
                    for key in properties.shared_model_catalog.DEFAULT_MODEL_KEYS
                ),
            ),
        ):
            status = properties.ai_status()
            self.assertFalse(status["ready"])
            self.assertEqual(
                properties.ai_setup_label(status), "Set Up AI Server…"
            )


    def test_setup_ai_environment_selects_the_needed_install_step(self):
        calls = []
        ops = SimpleNamespace(
            anyimage=SimpleNamespace(
                install_environment=lambda *_args: (
                    calls.append("official") or {"FINISHED"}
                ),
                install_environment_mirror=lambda *_args: (
                    calls.append("mirror") or {"FINISHED"}
                ),
                download_required_models=lambda *_args: (
                    calls.append("models") or {"FINISHED"}
                ),
            )
        )
        operator = self.ai_setup.SetupAIEnvironment()
        with patch.object(self.fake_bpy, "ops", ops, create=True):
            operator.use_mirror = True
            with patch.object(
                self.ai_setup,
                "ai_status",
                return_value={
                    "environment_ready": False,
                    "missing_models": ("MOGE2_VITS_NORMAL", "BIREFNET_LITE"),
                    "ready": False,
                },
            ):
                self.assertEqual(operator.execute(None), {"FINISHED"})

            with patch.object(
                self.ai_setup,
                "ai_status",
                return_value={
                    "environment_ready": True,
                    "missing_models": ("BIREFNET_LITE",),
                    "ready": False,
                },
            ):
                self.assertEqual(operator.execute(None), {"FINISHED"})

        self.assertEqual(calls, ["mirror", "models"])


    def test_ai_environment_ui_types_are_registered(self):
        self.assertIn(self.ai_setup.SetupAIEnvironment, self.anyimage.CLASSES)
        self.assertIn(
            self.ai_setup.OpenAIEnvironmentSettings,
            self.anyimage.CLASSES,
        )


    def test_ui_reads_required_model_files_without_starting_server(self):
        properties = importlib.import_module("anyimage.properties")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            moge = root / "models" / "moge-2-vits-normal-onnx"
            lite = root / "models" / "birefnet-lite"
            wdn = root / "models" / "realesr-general-wdn-x4v3"
            moge.mkdir(parents=True)
            lite.mkdir(parents=True)
            wdn.mkdir(parents=True)
            (moge / "model.onnx").touch()
            (lite / "model.onnx").touch()
            (lite / "LICENSE.txt").touch()
            (wdn / "realesr-general-wdn-x4v3.onnx").touch()

            with (
                patch.object(
                    self.anyimage.runtime,
                    "storage_root",
                    return_value=root,
                ),
                patch.object(
                    self.anyimage.runtime,
                    "resource",
                    side_effect=AssertionError("UI must not start the Server"),
                ),
            ):
                self.assertEqual(properties.ai_status()["missing_models"], ())
