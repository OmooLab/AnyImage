import importlib
import json
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class JobOperatorTest(BlenderTestCase):
    def test_runtime_submits_job_type_and_plain_dict(self):
        calls = []
        submitted = threading.Event()

        class Controller:
            def submit(self, job_type, parameters):
                calls.append((job_type, parameters))
                submitted.set()
                return {"job_id": "job", "directory": "."}

            def cancel(self, _job_id):
                pass

            def mark_job_complete(self, _job_id):
                pass

        class Example(self.runtime.JobOperatorBase):
            job_type = "example"
            value: object()

            def controller(self, _runtime):
                return Controller()

        timers = []
        window_manager = SimpleNamespace(
            progress_begin=lambda *_args: None,
            progress_update=lambda _value: None,
            event_timer_add=lambda *_args, **_kwargs: (
                timers.append(object()) or timers[-1]
            ),
            event_timer_remove=lambda _timer: None,
            modal_handler_add=lambda _operator: None,
        )
        context = SimpleNamespace(
            window_manager=window_manager,
            window=object(),
        )
        operator = Example()
        operator.value = 9

        self.assertEqual(operator.execute(context), {"RUNNING_MODAL"})
        self.assertTrue(submitted.wait(1.0))
        self.assertEqual(calls, [("example", {"value": 9})])


    def test_runtime_owns_environment_and_storage_paths(self):
        runtime = self.anyimage.runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runtime, "storage_root_factory", root):
                self.assertEqual(runtime.storage_root(), root.resolve())
                self.assertEqual(runtime.environment_directory(), root / ".venv")
                self.assertEqual(
                    runtime.install_status_path(), root / "install-status.json"
                )
                self.assertEqual(runtime.install_log_path(), root / "install.log")
                self.assertEqual(runtime.server_log_path(), root / "server.log")


    def test_runtime_checks_its_environment_dictionary_hash(self):
        runtime = self.anyimage.runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = (
                root
                / ".venv"
                / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            )
            python.parent.mkdir(parents=True)
            python.touch()
            (root / "manifest.json").write_text(
                json.dumps({"environment_hash": runtime.environment_hash}),
                encoding="utf-8",
            )
            with patch.object(runtime, "storage_root_factory", root):
                self.assertTrue(runtime.environment_ready())


    def test_runtime_builds_the_standard_installer_command(self):
        runtime = self.anyimage.runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(runtime, "storage_root_factory", root):
                command = runtime.install_command()
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(Path(command[1]).name, "environment.py")
        self.assertEqual(Path(command[1]).parent.name, "installer")
        self.assertIn("--storage-root", command)
        self.assertIn("--config", command)


    def test_server_request_returns_job_result_and_calls_response(self):
        controller_type = importlib.import_module(
            "blendjob.controller"
        ).ServerController
        controller = controller_type.__new__(controller_type)
        statuses = iter(
            (
                {"state": "running", "progress": 0.5},
                {
                    "state": "succeeded",
                    "progress": 1.0,
                    "result": {"value": 7},
                },
            )
        )
        controller.submit = lambda _job_type, _parameters: {
            "job_id": "job",
            "directory": ".",
        }
        controller.status = lambda _job_id: next(statuses)
        controller.mark_job_complete = lambda _job_id: None
        responses = []

        result = controller.request(
            "example",
            {"input": 3},
            response=responses.append,
            poll_interval=0.01,
        )

        self.assertEqual(result.value, {"value": 7})
        self.assertEqual(responses, [result])

