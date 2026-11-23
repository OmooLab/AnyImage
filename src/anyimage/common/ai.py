"""Shared Blender-side AI setup, validation, UI, and Job parameters."""

from pathlib import Path

import bpy

from ..ai_preferences import configured_device, configured_geometry_model
from ..preferences import addon_preferences
from ..runtime import runtime
from ..server import model_catalog as shared_model_catalog


def server_root(location):
    if not str(location).strip():
        raise ValueError("Choose a Server Location")
    selected = Path(location).expanduser().resolve()
    root = next(
        (path for path in (selected, *selected.parents) if path.name.lower() == ".anyimage"),
        selected / ".anyimage",
    )
    if root.resolve() != root:
        raise ValueError("Choose a location with a regular .anyimage directory")
    return root


def inspect_installation(root):
    status = runtime.inspect_installation(root)
    missing = []
    for key in shared_model_catalog.DEFAULT_MODEL_KEYS:
        model = shared_model_catalog.get_downloadable_model(key)
        if not model_files_installed(root, model):
            missing.append(key)
    return {**status, "missing_models": tuple(missing)}


def model_files_installed(root, model):
    directory = Path(root) / "models" / model.directory_name
    try:
        return all((directory / name).stat().st_size == size for name, size, _checksum in model.files)
    except OSError:
        return False


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


def require_environment():
    if not runtime.is_ready():
        raise RuntimeError("Install the Any Image Environment first")


def invoke_ai_setup_if_needed(operator):
    status = ai_status()
    if status["ready"]:
        return None
    try:
        if status["environment_ready"]:
            return bpy.ops.anyimage.download_required_models("INVOKE_DEFAULT")
        return bpy.ops.anyimage.setup_ai_server("INVOKE_DEFAULT")
    except RuntimeError as error:
        operator.report({"ERROR"}, str(error).removeprefix("Error: ").strip())
        return {"CANCELLED"}


def require_model(model_key):
    model = shared_model_catalog.DOWNLOADABLE_MODELS.get(model_key)
    if model is None:
        raise RuntimeError(f"Unknown model: {model_key}")
    errors = runtime.resource("model_manager").get("validation_errors", {})
    if errors.get(model_key) or not model_files_installed(runtime.storage_root(), model):
        raise RuntimeError(f"Download {model.label} first")


def model_job_parameters(model):
    require_environment()
    require_model(model)
    return {"model": model, "device": configured_device()}


def geometry_job_parameters(context):
    model = configured_geometry_model(context)
    parameters = model_job_parameters(model)
    preferences = addon_preferences(context)
    parameters["resolution_level"] = int(getattr(preferences, "geometry_resolution_level", 3))
    if model == "MOGE3_VITL":
        parameters["refine_steps"] = int(getattr(preferences, "geometry_refine_steps", 1))
    return parameters
