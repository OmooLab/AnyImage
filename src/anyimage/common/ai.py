"""Shared Blender-side AI setup, validation, UI, and Job parameters."""

import bpy

from ..server.media.input import validate_input_path

from ..preferences import addon_preferences
from ..runtime import runtime
from ..server import model_catalog as shared_model_catalog
from .server_location import model_files_installed


def model_catalog():
    """Read local model installation state and the current server snapshot."""
    errors = runtime.resource("model_manager").get("validation_errors", {})
    root = runtime.storage_root()
    return tuple(
        {
            **shared_model_catalog.model_record(model, model_files_installed(root, model)),
            "validation_error": errors.get(model.key, ""),
        }
        for model in shared_model_catalog.DOWNLOADABLE_MODELS.values()
    )


def ai_status(models=None):
    environment_ready = runtime.is_ready()
    if models is None:
        models = model_catalog()
    ready_models = {
        model["key"] for model in models
        if model.get("installed") and not model.get("validation_error")
    }
    missing_models = tuple(
        key for key in shared_model_catalog.DEFAULT_MODEL_KEYS if key not in ready_models
    )
    return {
        "environment_ready": environment_ready,
        "missing_models": missing_models,
        "ready": environment_ready and not missing_models,
    }


def ai_ready():
    return ai_status()["ready"]


def draw_ai_setup(layout, status=None):
    from ..operators.ai_setup import SetupAIServer, DownloadRequiredModels

    if status is None:
        status = ai_status()
    if not status["ready"]:
        operator = DownloadRequiredModels if status["environment_ready"] else SetupAIServer
        layout.operator(operator.bl_idname, icon="IMPORT")
    return status


def draw_ai_property(layout, owner, name, status):
    row = layout.row()
    row.enabled = status["ready"]
    row.prop(owner, name)


def require_input_path(value):
    return validate_input_path(bpy.path.abspath(value))


def report_ai_error(operator, error):
    """Report the underlying reason from a nested Blender operator."""
    operator.report({"ERROR"}, str(error).removeprefix("Error: ").strip())


def production_device():
    return getattr(addon_preferences(), "device", "AUTO")


def require_environment():
    if not runtime.is_ready():
        raise RuntimeError("Install the AnyImage Environment first")


def invoke_ai_setup_if_needed(operator):
    status = ai_status()
    if status["ready"]:
        return None
    try:
        if status["environment_ready"]:
            return bpy.ops.anyimage.download_required_models("INVOKE_DEFAULT")
        return bpy.ops.anyimage.setup_ai_server("INVOKE_DEFAULT")
    except RuntimeError as error:
        report_ai_error(operator, error)
        return {"CANCELLED"}


def require_model(model_key):
    model = next((item for item in model_catalog() if item["key"] == model_key), None)
    if model is None:
        raise RuntimeError(f"Unknown model: {model_key}")
    if not model["installed"] or model.get("validation_error"):
        raise RuntimeError(f"Download {model['label']} first")
    return model


def geometry_job_parameters(path, model, resolution_level):
    return {
        "input": str(path),
        "model": model,
        "resolution_level": int(resolution_level),
        "device": production_device().lower(),
    }
