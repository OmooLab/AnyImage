import importlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class ServerLocationTest(BlenderTestCase):
    def setUp(self):
        super().setUp()
        self.storage = importlib.import_module("anyimage.common.server_location")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "old" / ".anyimage"
        self.target = self.base / "new" / ".anyimage"
        self.source.mkdir(parents=True)
        (self.source / "models").mkdir()
        (self.source / "models" / "model.onnx").write_bytes(b"model contents")
        (self.source / "server.log").write_text("log", encoding="utf-8")

    def test_location_accepts_parent_installation_and_descendant_folders(self):
        self.assertEqual(self.storage.server_root(self.base), self.base / ".anyimage")
        for selected in (self.source.parent, self.source, self.source / "models", self.source / "models/nested"):
            with self.subTest(selected=selected):
                self.assertEqual(self.storage.server_root(selected), self.source)
        with self.assertRaises(ValueError):
            self.storage.server_root("")


    def test_inspection_adds_model_status_to_runtime_environment_status(self):
        with (
            patch.object(self.anyimage.runtime, "inspect_installation", return_value={"environment_ready": True}) as inspect,
            patch.object(self.storage, "DEFAULT_MODEL_KEYS", ("first", "second")),
            patch.object(self.storage, "get_downloadable_model", side_effect=lambda key: key),
            patch.object(self.storage, "model_files_installed", side_effect=(True, False)),
        ):
            status = self.storage.inspect_installation(self.target)
        inspect.assert_called_once_with(self.target)
        self.assertEqual(status, {"environment_ready": True, "missing_models": ("second",)})

    def test_save_failure_restores_previous_preference(self):
        preferences = self.fake_bpy.context.preferences.addons["anyimage"].preferences
        previous = preferences.storage_root
        ops = SimpleNamespace(wm=SimpleNamespace(save_userpref=Mock(return_value={"CANCELLED"})))
        with patch.object(self.fake_bpy, "ops", ops, create=True):
            with self.assertRaisesRegex(RuntimeError, "save"):
                self.anyimage.ai_preferences.storage_root(self.target)
        self.assertEqual(preferences.storage_root, previous)

    def test_save_persists_new_location(self):
        ops = SimpleNamespace(wm=SimpleNamespace(save_userpref=Mock(return_value={"FINISHED"})))
        with patch.object(self.fake_bpy, "ops", ops, create=True):
            self.assertEqual(self.anyimage.ai_preferences.storage_root(self.target), self.target)
        self.assertEqual(self.anyimage.ai_preferences.storage_root(), self.target)
        ops.wm.save_userpref.assert_called_once_with()
