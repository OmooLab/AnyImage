"""Verify cleanup confirmation and Blender-side reference protection."""

import importlib
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class JobFilesTest(BlenderTestCase):
    def test_cleanup_requires_confirmation_and_rechecks_busy_state(self):
        module = importlib.import_module("anyimage.operators.job_files")
        operator = module.ClearJobFiles()
        operator.report = Mock()
        preview = {"jobs": ["a" * 32], "bytes": 123, "skipped": 0, "failed": []}
        client = SimpleNamespace(preview_job_files=Mock(return_value=preview), clear_job_files=Mock(return_value=preview))
        connection = SimpleNamespace(instance_id="one", client=client)
        runtime = SimpleNamespace(environment_ready=lambda: True, server_busy=lambda: False,
                                  server_status=lambda: {"state": "READY"},
                                  server=SimpleNamespace(ensure=lambda: connection, connection=connection))
        context = SimpleNamespace(window_manager=SimpleNamespace(invoke_props_dialog=Mock(return_value={"RUNNING_MODAL"})))
        with patch.object(module, "runtime", runtime), patch.object(module, "protected_image_paths", return_value=["C:/protected.png"]):
            assert operator.execute(context) == {"CANCELLED"}
            client.clear_job_files.assert_not_called()
            assert operator.invoke(context, None) == {"RUNNING_MODAL"}
            client.preview_job_files.assert_called_once_with(["C:/protected.png"])
            runtime.server_busy = lambda: True
            assert operator.execute(context) == {"CANCELLED"}
            client.clear_job_files.assert_not_called()
            runtime.server_busy = lambda: False
            assert operator.execute(context) == {"FINISHED"}
            client.clear_job_files.assert_called_once_with(preview["jobs"], ["C:/protected.png"])
            connection.instance_id = "restarted"
            assert operator.execute(context) == {"CANCELLED"}
            assert client.clear_job_files.call_count == 1

    def test_only_unpacked_image_paths_are_protected(self):
        module = importlib.import_module("anyimage.operators.job_files")
        images = [SimpleNamespace(filepath="C:/jobs/a/normal.png", library=None, packed=False),
                  SimpleNamespace(filepath="C:/jobs/b/depth.exr", library=None, packed=True),
                  SimpleNamespace(filepath="", library=None, packed=False)]
        fake = SimpleNamespace(data=SimpleNamespace(images=images),
                               path=SimpleNamespace(abspath=lambda path, **kwargs: path))
        with patch.object(module, "bpy", fake), patch.object(module, "image_is_packed", side_effect=lambda image: image.packed):
            paths = module.protected_image_paths()
        assert len(paths) == 1 and paths[0].replace("\\", "/").endswith("jobs/a/normal.png")
