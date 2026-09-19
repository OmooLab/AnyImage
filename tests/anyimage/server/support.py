from tests.support.paths import PROJECT_ROOT
import sys
from pathlib import Path


def load_server_module(name):
    addon_directory = PROJECT_ROOT / "src" / "anyimage"
    sys.path.insert(0, str(addon_directory))
    try:
        return __import__(f"server.{name}", fromlist=[name])
    finally:
        sys.path.remove(str(addon_directory))


class FakeModels:
    def __init__(self, directory="BEN2-ONNX"):
        self.model_directory = Path(directory)

    def directory(self, _model):
        return self.model_directory

    def get_background(self, _model_directory, _device):
        from server.models.onnx_ben2 import create_session

        return create_session(self.model_directory, "cpu"), 0.0


    def get_upscale(self, _model_directory, _device):
        return object()


class FakeJobContext:
    def __init__(self, directory, job_type, models=None):
        self.directory = Path(directory)
        self.job_type = job_type
        self.models = models or FakeModels()
        self.status = {}
        self.logs = []

    def resource(self, name):
        if name != "model_manager":
            raise KeyError(name)
        return self.models

    def progress(self, progress, message, **details):
        self.status = {
            "progress": progress,
            "message": message,
            **details,
        }

    def log(self, message, *, level="INFO"):
        self.logs.append((level, message))

    def check_cancelled(self):
        return None
