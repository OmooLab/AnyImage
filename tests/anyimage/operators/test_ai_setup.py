import importlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class AiSetupTest(BlenderTestCase):
    def test_setup_checks_changed_location_before_starting(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        operator = self.ai_setup.SetupAIServer()
        operator.location = str(root / "first")
        operator.report = Mock()
        with patch.object(self.ai_setup, "inspect_installation", return_value={"environment_ready": True, "missing_models": ()}) as inspect:
            self.assertTrue(operator.check(None))
            operator.location = str(root / "second")
            inspect.side_effect = ValueError("Invalid location")
            with patch.object(self.ai_setup.JobOperatorBase, "execute") as execute:
                self.assertEqual(operator.execute(None), {"CANCELLED"})
                execute.assert_not_called()
            inspect.assert_called_with(root / "second/.anyimage")

    def test_setup_preview_checks_each_selected_location_only_once(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        operator = self.ai_setup.SetupAIServer()
        operator.layout = Mock()
        operator.location = str(root / "first/.anyimage/models")
        status = {"environment_ready": True, "missing_models": ("BIREFNET_LITE",)}
        with (
            patch.object(self.ai_setup, "inspect_installation", return_value=status) as inspect,
            patch.object(self.ai_setup, "model_record", side_effect=AssertionError("Preview must use static labels")),
        ):
            operator.draw(None)
            operator.draw(None)
            inspect.assert_called_once_with(root / "first/.anyimage")
            operator.location = str(root / "second/.anyimage")
            operator.draw(None)
            self.assertEqual(inspect.call_count, 2)
            inspect.assert_called_with(root / "second/.anyimage")

    def test_setup_rechecks_directory_after_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            operator = self.ai_setup.SetupAIServer()
            operator.layout = Mock()
            operator.location = directory
            operator.use_mirror = False
            operator.draw(None)
            target = Path(directory) / ".anyimage"
            target.mkdir()
            (target / "unrelated.txt").write_text("unrelated", encoding="utf-8")
            setup = Mock(side_effect=RuntimeError("The target is not a BlendJob installation"))
            operator.report = Mock()
            with patch.object(self.fake_bpy, "ops", SimpleNamespace(anyimage=SimpleNamespace(setup_server=setup)), create=True):
                self.assertEqual(operator.execute(None), {"CANCELLED"})
                setup.assert_called_once_with(directory=str(target), use_mirror=False)

    def test_post_setup_downloads_only_missing_or_corrupt_models(self):
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
                    self.runtime.prepare_models(SimpleNamespace(request=request, online=True))
                self.assertEqual(
                    [call.args[1] for call in download.call_args_list],
                    [] if state == "ready" else [affected],
                )

    def test_post_setup_propagates_model_preparation_failure(self):
        request = Mock(side_effect=RuntimeError("network unavailable"))
        with self.assertRaisesRegex(RuntimeError, "network unavailable"):
            self.runtime.prepare_models(SimpleNamespace(request=request, online=True))
        request.assert_called_once()


    def test_required_model_operator_requests_all_default_models(self):
        operator = self.ai_setup.DownloadRequiredModels()
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
                    {"key": "MOGE2_VITS_NORMAL", "installed": True},
                    {"key": "BIREFNET_LITE", "installed": False},
                    {
                        "key": "REALESRGAN_GENERAL_WDN_X4V3",
                        "installed": True,
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
                    {"key": key, "installed": True}
                    for key in properties.shared_model_catalog.DEFAULT_MODEL_KEYS
                ),
            ),
        ):
            status = properties.ai_status()
            self.assertFalse(status["ready"])
            self.assertEqual(
                properties.ai_setup_label(status), "Set Up AI Server…"
            )


    def test_setup_prepares_the_selected_location_without_changing_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            operator = self.ai_setup.SetupAIServer()
            operator.location = directory
            operator.use_mirror = True
            self.fake_bpy.context.preferences.addons["anyimage"].preferences.storage_root = str(Path(directory) / "current")
            original = self.anyimage.preferences.storage_root()
            setup = Mock(return_value={"RUNNING_MODAL"})
            with patch.object(self.fake_bpy, "ops", SimpleNamespace(anyimage=SimpleNamespace(setup_server=setup)), create=True):
                self.assertEqual(operator.execute(None), {"FINISHED"})
            setup.assert_called_once_with(directory=str(Path(directory) / ".anyimage"), use_mirror=True)
            self.assertEqual(self.anyimage.preferences.storage_root(), original)


    def test_ai_environment_ui_types_are_registered(self):
        self.assertIn(self.ai_setup.SetupAIServer, self.anyimage.CLASSES)
        self.assertIn(
            self.ai_setup.OpenAIEnvironmentSettings,
            self.anyimage.CLASSES,
        )

    def test_model_preparation_passes_offline_policy_to_server(self):
        request = Mock()
        self.runtime.prepare_models(SimpleNamespace(request=request, online=False))
        self.assertFalse(request.call_args.args[1]["online"])

    def test_unload_models_is_only_available_while_server_is_ready(self):
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
                self.assertEqual(self.ai_setup.UnloadModels.poll(None), expected)


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
