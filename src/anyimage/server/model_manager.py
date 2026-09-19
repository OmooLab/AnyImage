import gc
import hashlib
import time
from pathlib import Path
from types import SimpleNamespace

from . import model_catalog
from .model_download import download_model


class ModelSessionCache:
    """Cache ONNX sessions shared by Jobs in one Server process."""

    def __init__(self):
        self.background_model = None
        self.background_key = None
        self.moge_model = None
        self.moge_key = None
        self.upscale_model = None
        self.upscale_key = None

    def get_background(self, model_dir, device):
        from .models.background import inference_device

        requested_device = inference_device(model_dir, device)
        key = (str(Path(model_dir).resolve()), requested_device, "onnx")
        if self.background_model is not None and self.background_key == key:
            return self.background_model, 0.0
        self.release_background()
        return self._load_background(model_dir, requested_device, key)

    def _load_background(self, model_dir, requested_device, key):
        from .models.background import model_adapter

        started = time.perf_counter()
        model = model_adapter(model_dir).create_session(model_dir, requested_device)
        self.background_model = model
        self.background_key = key
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return model, elapsed_ms


    def get_moge(self, model_dir, requested_device):
        from .models.onnx_moge2 import create_session

        if Path(model_dir).name == "moge-3-vitl-onnx":
            from .models.onnx_moge3 import create_session

        key = (str(Path(model_dir).resolve()), requested_device, "onnx")
        if self.moge_model is not None and self.moge_key == key:
            return self.moge_model
        self.release_geometry()
        model = create_session(model_dir, requested_device)
        self.moge_model = model
        self.moge_key = key
        return model

    def get_upscale(self, model_dir, requested_device):
        from .models.onnx_upscale import create_session

        key = (str(Path(model_dir).resolve()), requested_device, "onnx")
        if self.upscale_model is not None and self.upscale_key == key:
            return self.upscale_model
        self.release_upscale()
        model = create_session(model_dir, requested_device)
        self.upscale_model = model
        self.upscale_key = key
        return model

    def release_background(self):
        self.background_model = None
        self.background_key = None
        self._release_runtime_cache()

    def release_geometry(self):
        self.moge_model = None
        self.moge_key = None
        self._release_runtime_cache()

    def release_upscale(self):
        self.upscale_model = None
        self.upscale_key = None
        self._release_runtime_cache()

    def close(self):
        self.background_model = None
        self.moge_model = None
        self.upscale_model = None
        self.background_key = None
        self.moge_key = None
        self.upscale_key = None
        self._release_runtime_cache()

    def snapshot(self):
        geometry_key = self.moge_key
        return {
            "background": Path(self.background_key[0]).name if self.background_key else "",
            "geometry": Path(geometry_key[0]).name if geometry_key else "",
            "upscale": (Path(self.upscale_key[0]).name if self.upscale_key else ""),
        }

    def _release_runtime_cache(self):
        gc.collect()


class ModelManager:
    """Own downloaded model files and loaded inference sessions."""

    def __init__(self, models_directory):
        self.models_directory = Path(models_directory)
        self.sessions = ModelSessionCache()
        self.verified_files = {}

    def directory(self, model_key):
        model = model_catalog.get_downloadable_model(model_key)
        return self.models_directory / model.directory_name

    def ready(self, model_key):
        model = model_catalog.get_downloadable_model(model_key)
        directory = self.directory(model_key)
        if model_key in {"MOGE3_VITL", "HAT_GAN_X4_SHARPER", *model_catalog.BACKGROUND_MODELS}:
            for filename, size, checksum in model.r2_files:
                path = directory / filename
                try:
                    stat = path.stat()
                    if stat.st_size != size:
                        return False
                    identity = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
                    cached = self.verified_files.get(path)
                    # Windows can coalesce timestamps for immediately repeated writes.
                    cacheable = size >= 1024 * 1024 and time.time_ns() - stat.st_mtime_ns > 1_000_000_000
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
        return all(any(directory.glob(pattern)) for pattern in model.ready_patterns)

    def get_background(self, model_dir, device):
        return self.sessions.get_background(model_dir, device)


    def get_moge(self, model_dir, device):
        return self.sessions.get_moge(model_dir, device)

    def get_upscale(self, model_dir, device):
        return self.sessions.get_upscale(model_dir, device)

    def release_upscale(self):
        self.sessions.release_upscale()

    def snapshot(self):
        return {"loaded": self.sessions.snapshot()}

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
        args = SimpleNamespace(
            repository=model.huggingface_repository,
            model_dir=str(self.directory(model_key)),
            progress=progress,
            cancel_check=context.check_cancelled,
            label=model.label,
            allow_pattern=list(model.download_patterns),
            required_pattern=list(model.ready_patterns),
            r2_directory=model.r2_directory,
            r2_file=[
                f"{filename}|{size}|{checksum}"
                for filename, size, checksum in model.r2_files
            ],
        )
        context.check_cancelled()
        download_model(args)
        context.check_cancelled()
