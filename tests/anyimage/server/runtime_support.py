import importlib
import tempfile
import time
import unittest
from pathlib import Path


class ServerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_module = importlib.import_module("server")
        importlib.import_module("server.geometry.prediction_artifacts")
        importlib.import_module("server.jobs.cutout")
        from blendjob import JobServer
        from server.model_manager import ModelManager, ModelSessionCache
        from server.models import onnx_runtime

        cls.JobServer = JobServer

        cls.ModelManager, cls.ModelSessionCache = ModelManager, ModelSessionCache
        cls.onnx_runtime = onnx_runtime
        cls.app_module = importlib.import_module("server.app")


    def setUp(self):
        self.jobs_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.jobs_temp.cleanup)
        self.storage_root = Path(self.jobs_temp.name)


    def create_cache(self):
        return self.ModelSessionCache()


    def create_server(self):
        source = self.server_module.server
        server = self.JobServer("AnyImage Job Server", storage_root=self.storage_root)
        self.addCleanup(server.close)
        server.handlers.update(source.handlers)
        server.resource_factories.update(source.resource_factories)
        server.bind(self.storage_root)
        return server


    def wait_for_job(self, context, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if context._snapshot()["state"] in {"succeeded", "failed", "cancelled"}:
                return context._snapshot()
            time.sleep(0.01)
        self.fail(f"Job did not finish: {context._snapshot()}")
