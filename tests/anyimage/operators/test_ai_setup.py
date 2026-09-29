import importlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class AiSetupTest(BlenderTestCase):
    def test_post_install_downloads_only_missing_or_corrupt_models(self):
        import hashlib
        from dataclasses import replace
        from server import app, model_catalog
        from server.model_manager import ModelManager

        content = b"verified"
        specs = {
            key: replace(
                model_catalog.get_downloadable_model(key),
                files=(("model.onnx", len(content), hashlib.sha256(content).hexdigest()),),
            )
            for key in model_catalog.DEFAULT_MODEL_KEYS
        }
        for state in ("ready", "missing", "corrupt"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                manager = ModelManager(directory)
                for spec in specs.values():
                    path = manager.directory(spec.key) / "model.onnx"
                    path.parent.mkdir(parents=True)
                    path.write_bytes(content)
                affected = model_catalog.DEFAULT_MODEL_KEYS[0]
                path = manager.directory(affected) / "model.onnx"
                if state == "missing":
                    path.unlink()
                elif state == "corrupt":
                    path.write_bytes(b"damaged!")
                context = SimpleNamespace(resource=lambda _: manager, progress=Mock())

                def request(job_type, parameters):
                    self.assertEqual(job_type, "download-required-models")
                    return app.download_required_models(context, parameters)

                with (
                    patch.dict(model_catalog.DOWNLOADABLE_MODELS, specs),
                    patch.object(manager, "_download") as download,
                ):
                    self.runtime.post_install(SimpleNamespace(request=request))
                self.assertEqual(
                    [call.args[1] for call in download.call_args_list],
                    [] if state == "ready" else [affected],
                )

    def test_post_install_propagates_model_preparation_failure(self):
        request = Mock(side_effect=RuntimeError("network unavailable"))
        with self.assertRaisesRegex(RuntimeError, "network unavailable"):
            self.runtime.post_install(SimpleNamespace(request=request))
        request.assert_called_once()


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

    def test_clear_models_is_only_available_while_server_is_ready(self):
        for state, expected in (
            ("READY", True),
            ("BUSY", False),
            ("STOPPED", False),
        ):
            with (
                self.subTest(state=state),
                patch.object(
                    self.anyimage.runtime,
                    "server_status",
                    return_value={"state": state},
                ),
            ):
                self.assertEqual(self.ai_setup.ClearModels.poll(None), expected)


    def test_ui_reads_required_model_files_without_starting_server(self):
        properties = importlib.import_module("anyimage.properties")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            from dataclasses import replace

            catalog = properties.shared_model_catalog
            specs = {
                key: replace(catalog.get_downloadable_model(key), files=tuple(
                    (name, 1, "unused") for name, _, _ in catalog.get_downloadable_model(key).files
                ))
                for key in catalog.DEFAULT_MODEL_KEYS
            }
            for spec in specs.values():
                for name, _, _ in spec.files:
                    path = root / "models" / spec.directory_name / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"a")

            with (
                patch.dict(catalog.DOWNLOADABLE_MODELS, specs),
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
                path.write_bytes(b"")
                self.assertIn(spec.key, properties.ai_status()["missing_models"])
