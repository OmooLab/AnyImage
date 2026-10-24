from .properties import (
    AnyImageSettings as SharedSettings,
)
import bpy
import platform
import sys
from .common.server_location import model_files_installed
from .runtime import runtime
from .server import model_catalog as shared_model_catalog

DEVICE_LABELS = {
    "cuda": ("CUDA", "NVIDIA CUDA"),
    "directml": ("DirectML", "Windows GPU (DirectML)"),
    "coreml": ("CoreML", "Apple CoreML"),
    "cpu": ("CPU", "CPU"),
}


def supports_coreml():
    return sys.platform == "darwin" and platform.machine().lower() in {
        "arm64",
        "aarch64",
    }


def supported_devices():
    if sys.platform == "win32":
        return ["directml", "cpu"]
    return ["cpu", "coreml"] if supports_coreml() else ["cpu"]


def device_enum_items(_owner, _context):
    return [
        (name.upper(), *DEVICE_LABELS[name], index)
        for index, name in enumerate(supported_devices())
    ]


def models_status():
    status = runtime.server_status().get("resources", {}).get("model_manager", {})
    errors = status.get("validation_errors", {})
    return {
        "catalog": tuple(
            {
                **shared_model_catalog.model_record(
                    model, model_files_installed(runtime.storage_root(), model)
                ),
                "validation_error": errors.get(model.key, ""),
            }
            for model in shared_model_catalog.DOWNLOADABLE_MODELS.values()
        ),
        "loaded": status.get("loaded", {}),
    }


def model_ready(model_key):
    return any(
        model.get("key") == model_key
        and model.get("installed")
        and not model.get("validation_error")
        for model in models_status().get("catalog", ())
    )


def ai_status():
    environment_ready = runtime.environment_ready()
    ready_models = {
        model["key"]
        for model in model_catalog()
        if model.get("installed") and not model.get("validation_error")
    }
    missing_models = tuple(
        model_key
        for model_key in shared_model_catalog.DEFAULT_MODEL_KEYS
        if model_key not in ready_models
    )
    return {
        "environment_ready": environment_ready,
        "missing_models": missing_models,
        "ready": environment_ready and not missing_models,
    }


def ai_ready():
    return ai_status()["ready"]


def ai_setup_label(status=None):
    if status is None:
        status = ai_status()
    return "Download Required Models…" if status["environment_ready"] else "Set Up AI Server…"


def model_download_size(model_key):
    model = shared_model_catalog.get_downloadable_model(model_key)
    return sum(size for _path, size, _checksum in model.files)


def model_catalog():
    return models_status().get("catalog", ())


def model_record(model_key):
    return next(
        (model for model in model_catalog() if model.get("key") == model_key),
        None,
    )


def _model_items(models):
    return [
        (
            model["key"],
            f"{model['tier']} | {model['label']}",
            bpy.app.translations.pgettext_tip("{description}; license: {license}").format(
                description=bpy.app.translations.pgettext_tip(model["description"]),
                license=model["license"],
            ),
            model["enum_value"],
        )
        for model in models
    ]


def geometry_model_enum_items(_owner, _context):
    models = [model for model in model_catalog() if model.get("family") == "moge"]
    return _model_items(models)


def upscale_model_label(model_key):
    model = shared_model_catalog.UPSCALE_MODELS.get(model_key)
    return model.label if model is not None else model_key


class AnyImageSettings(SharedSettings):
    cutout_generate_normal: bpy.props.BoolProperty(
        name="Normal Map",
        description=(
            "Generate a normal map to add surface detail under lighting for Flat and Solid shapes. "
            "Depth Solid and Depth Symmetry always generate normal maps."
        ),
        default=False,
    )
