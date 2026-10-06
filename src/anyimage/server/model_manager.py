import gc
import hashlib
import time
from pathlib import Path

from . import model_catalog
from .model_download import download_model
from .models import model_adapter
from .models.onnx_runtime import OnnxResourceError


class ModelSessionCache:
    """Keep one loaded model per inference family."""

    def __init__(self):
        self.sessions = {}

    def get(self, model, directory, device):
        device = model.device or device
        key = (model.key, str(Path(directory).resolve()), device)
        cached = self.sessions.get(model.family)
        if cached is not None and cached[0] == key:
            return cached[1], 0.0
        del cached
        if self.sessions.pop(model.family, None) is not None:
            gc.collect()
        started = time.perf_counter()
        adapter = model_adapter(model.key)
        session = self._load_session(lambda: adapter.create_session(directory, device))
        self.sessions[model.family] = (key, session)
        return session, (time.perf_counter() - started) * 1000.0

    def close(self):
        self.sessions.clear()
        gc.collect()

    def release_model(self, model):
        cached = self.sessions.get(model.family)
        if cached is not None and cached[0][0] == model.key:
            self.sessions.pop(model.family)
            del cached
            gc.collect()

    def snapshot(self):
        return {
            name: self.sessions[family][0][0] if family in self.sessions else None
            for family, name in (
                ("background", "background"),
                ("moge", "geometry"),
                ("upscale", "upscale"),
            )
        }

    def _load_session(self, factory):
        try:
            return factory()
        except (OnnxResourceError, MemoryError):
            pass
        # Leave the exception scope before collecting failed session frames.
        self.close()
        return factory()


class ModelManager:
    """Own downloaded model files and loaded inference sessions."""

    def __init__(self, models_directory):
        self.models_directory = Path(models_directory)
        self.sessions = ModelSessionCache()
        self.verified_files = {}
        self.validation_errors = {}

    def directory(self, model_key):
        model = model_catalog.get_downloadable_model(model_key)
        return self.models_directory / model.directory_name

    def ready(self, model_key):
        model = model_catalog.get_downloadable_model(model_key)
        directory = self.directory(model_key)
        for filename, size, checksum in model.files:
            path = directory / filename
            try:
                stat = path.stat()
                if stat.st_size != size:
                    return False
                identity = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                cached = self.verified_files.get(path)
                # Windows can coalesce timestamps for immediately repeated writes.
                cacheable = (
                    size >= 1024 * 1024
                    and time.time_ns() - stat.st_mtime_ns > 1_000_000_000
                )
                if not cacheable or cached != (identity, checksum):
                    with path.open("rb") as stream:
                        actual = hashlib.file_digest(stream, "sha256").hexdigest()
                    if actual != checksum:
                        return False
                    if cacheable:
                        self.verified_files[path] = (identity, checksum)
            except OSError:
                return False
        return True

    def get_session(self, model_key, device):
        model = model_catalog.get_downloadable_model(model_key)
        if not self.ready(model_key):
            message = f"{model.label} files failed validation; download the model again"
            self.validation_errors[model_key] = message
            self.sessions.release_model(model)
            raise RuntimeError(message)
        self.validation_errors.pop(model_key, None)
        return self.sessions.get(model, self.directory(model_key), device)

    def snapshot(self):
        return {"loaded": self.sessions.snapshot(), "validation_errors": dict(self.validation_errors)}

    def clear(self):
        self.sessions.close()

    def close(self):
        self.sessions.close()

    def download(self, context, model_key):
        return self._download(context, model_key, context.progress)

    def download_missing(self, context, model_keys):
        missing = [key for key in model_keys if not self.ready(key)]
        if not missing:
            context.progress(1.0, "Required models are ready")
            return {"downloaded": []}

        total = len(missing)
        for index, model_key in enumerate(missing):

            def report(value, message, *, offset=index):
                context.progress((offset + value) / total, message)

            self._download(context, model_key, report)
        return {"downloaded": missing}

    def _download(self, context, model_key, progress):
        model = model_catalog.get_downloadable_model(model_key)
        context.check_cancelled()
        self.sessions.release_model(model)
        for filename, _size, _checksum in model.files:
            self.verified_files.pop(self.directory(model_key) / filename, None)
        download_model(model, self.directory(model_key), progress, context.check_cancelled)
        context.check_cancelled()
        self.validation_errors.pop(model_key, None)
