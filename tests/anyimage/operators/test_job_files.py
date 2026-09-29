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
        client = SimpleNamespace(request=Mock(return_value=preview))
        connection = SimpleNamespace(instance_id="one", client=client)
        runtime = SimpleNamespace(environment_ready=lambda: True, server_busy=lambda: False,
                                  server_status=lambda: {"state": "READY"},
                                  server=SimpleNamespace(ensure=lambda: connection, connection=connection))
        context = SimpleNamespace(window_manager=SimpleNamespace(invoke_props_dialog=Mock(return_value={"RUNNING_MODAL"})))
        with patch.object(module, "runtime", runtime), patch.object(module, "protected_image_paths", return_value=["C:/protected.png"]):
            assert operator.execute(context) == {"CANCELLED"}
            client.request.assert_not_called()
            assert operator.invoke(context, None) == {"RUNNING_MODAL"}
            assert client.request.call_args.args[1] == "/job-files/preview"
            runtime.server_busy = lambda: True
            assert operator.execute(context) == {"CANCELLED"}
            assert client.request.call_count == 1
            runtime.server_busy = lambda: False
            assert operator.execute(context) == {"FINISHED"}
            assert client.request.call_args.args[1] == "/job-files/clear"
            assert client.request.call_args.args[2]["protected_paths"] == ["C:/protected.png"]
            connection.instance_id = "restarted"
            assert operator.execute(context) == {"CANCELLED"}
            assert client.request.call_count == 2

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
