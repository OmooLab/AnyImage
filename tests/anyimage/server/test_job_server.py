import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.anyimage.server.runtime_support import ServerTestCase

class JobServerTest(ServerTestCase):
    def test_model_job_resource_failure_clears_cache_without_retry(self):
        error = self.onnx_runtime.OnnxResourceError("memory exhausted")
        manager = SimpleNamespace(clear=Mock())
        context = SimpleNamespace(resource=lambda _name: manager)
        handler = Mock(side_effect=error)

        with self.assertRaises(self.onnx_runtime.OnnxResourceError) as raised:
            self.app_module._run_model_job(handler, context, {"value": 1})

        self.assertIs(raised.exception, error)
        handler.assert_called_once_with(context, {"value": 1})
        manager.clear.assert_called_once_with()

    def test_model_job_success_and_ordinary_failure_keep_cache(self):
        manager = SimpleNamespace(clear=Mock())
        context = SimpleNamespace(resource=lambda _name: manager)
        success = Mock(return_value={"value": 1})

        self.assertEqual(
            self.app_module._run_model_job(success, context, {}),
            {"value": 1},
        )
        with self.assertRaisesRegex(RuntimeError, "invalid input"):
            self.app_module._run_model_job(
                Mock(side_effect=RuntimeError("invalid input")),
                context,
                {},
            )

        manager.clear.assert_not_called()

    def test_every_model_inference_job_uses_resource_failure_boundary(self):
        context = object()
        parameters = {"value": 1}
        jobs = (
            self.app_module.remove_background,
            self.app_module.upscale_image,
            self.app_module.generate_depth_plane_geometry,
            self.app_module.generate_cutout_artifacts,
            self.app_module.generate_panorama_geometry,
        )

        with patch.object(
            self.app_module,
            "_run_model_job",
            return_value={"result": True},
        ) as run:
            for job in jobs:
                self.assertEqual(job(context, parameters), {"result": True})

        self.assertEqual(run.call_count, len(jobs))

    def test_dedicated_server_runs_only_one_job_at_a_time(self):
        server = self.JobServer("Test", storage_root=self.storage_root)
        self.addCleanup(server.close)
        first_started = threading.Event()
        release_first = threading.Event()
        order = []

        @server.job("example")
        def example(_context, parameters):
            order.append(parameters["name"])
            if parameters["name"] == "first":
                first_started.set()
                release_first.wait(1.0)

        first = server.submit("example", {"name": "first"}, job_id="job")
        self.assertTrue(first_started.wait(1.0))
        second = server.submit("example", {"name": "second"}, job_id="other")

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertTrue(server.snapshot("instance")["busy"])
        self.assertEqual(server.snapshot("instance")["queued_jobs"], 1)
        release_first.set()
        self.wait_for_job(first)
        self.wait_for_job(second)
        self.assertEqual(order, ["first", "second"])


    def test_queued_job_can_be_cancelled_before_it_runs(self):
        server = self.JobServer("Test", storage_root=self.storage_root)
        self.addCleanup(server.close)
        first_started = threading.Event()
        release_first = threading.Event()
        executed = []

        @server.job("example")
        def example(_context, parameters):
            executed.append(parameters["name"])
            if parameters["name"] == "first":
                first_started.set()
                release_first.wait(1.0)

        first = server.submit("example", {"name": "first"})
        self.assertTrue(first_started.wait(1.0))
        second = server.submit("example", {"name": "second"})

        self.assertIs(server.cancel(second.job_id), second)
        release_first.set()
        self.wait_for_job(first)
        second_status = self.wait_for_job(second)

        self.assertEqual(second_status["state"], "cancelled")
        self.assertEqual(executed, ["first"])


    def test_cancelling_job_keeps_server_and_model_cache_alive(self):
        fake_models = SimpleNamespace(
            snapshot=lambda: {"loaded": {"background": "BEN2_BASE", "geometry": ""}},
            clear=lambda: None,
            close=lambda: None,
        )
        with patch.object(self.app_module, "ModelManager", return_value=fake_models):
            server = self.create_server()
        started = threading.Event()

        @server.job("cancellable")
        def cancellable(context, _parameters):
            started.set()
            while not context._is_cancelled():
                time.sleep(0.001)
            context.check_cancelled()

        context = server.submit("cancellable", {}, job_id="job")
        self.assertTrue(started.wait(1.0))
        self.assertIsNotNone(server.cancel("job"))
        self.assertTrue(context._is_cancelled())
        status = self.wait_for_job(context)

        self.assertEqual(status["state"], "cancelled")
        self.assertFalse(server.shutdown_event.is_set())
        self.assertEqual(
            server.snapshot("instance")["resources"]["model_manager"]["loaded"]["background"],
            "BEN2_BASE",
        )


    def test_job_progress_is_kept_in_server_memory(self):
        server = self.JobServer("Test", storage_root=self.storage_root)
        self.addCleanup(server.close)

        @server.job("example")
        def example(context, _parameters):
            context.progress(0.5, "Half way")

        context = server.submit("example", {})
        self.wait_for_job(context)

        self.assertRegex(context.job_id, r"^[0-9a-f]{32}$")
        self.assertEqual(context.directory.name, context.job_id)
        self.assertEqual(context._snapshot()["state"], "succeeded")
        self.assertEqual(context._snapshot()["progress"], 1.0)


    def test_runtime_storage_root_owns_the_jobs_directory(self):
        storage_root = self.storage_root
        server = self.JobServer("Test")
        self.addCleanup(server.close)
        server.bind(storage_root)

        @server.job("example")
        def example(_context, _parameters):
            return {"value": 42}

        context = server.submit("example", {})
        self.wait_for_job(context)

        self.assertEqual(server.jobs_directory, storage_root / "jobs")
        self.assertEqual(context.storage_root, storage_root.resolve())
        self.assertEqual(context._snapshot()["result"], {"value": 42})


    def test_job_server_owns_and_clears_shared_resources(self):
        events = []
        resource = SimpleNamespace(
            snapshot=lambda: {"loaded": "model"},
            clear=lambda: events.append("clear"),
            close=lambda: events.append("close"),
        )
        server = self.JobServer("Test", storage_root=self.storage_root)
        self.addCleanup(server.close)
        server.add_resource("model_manager", resource)

        @server.job("example")
        def example(context, _parameters):
            self.assertIs(context.resource("model_manager"), resource)
            release.wait(1.0)

        release = threading.Event()
        context = server.submit("example", {}, job_id="job")
        self.assertFalse(server.clear_resource("model_manager"))
        release.set()
        self.wait_for_job(context)
        self.assertTrue(server.clear_resource("model_manager"))
        server.close()

        self.assertEqual(
            server.snapshot("instance")["resources"]["model_manager"]["loaded"],
            "model",
        )
        self.assertEqual(events, ["clear", "close"])


    def test_server_registers_tasks_instead_of_model_names(self):
        server = self.create_server()
        self.assertEqual(
            set(server.handlers),
            {
                "download-model",
                "download-required-models",
                "remove-background",
                "upscale-image",
                "generate-depth-plane-geometry",
                "generate-panorama-geometry",
                "generate-cutout-artifacts",
            },
        )
