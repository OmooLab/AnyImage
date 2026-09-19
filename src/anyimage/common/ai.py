"""Shared Blender-side AI setup, validation, UI, and Job parameters."""

import bpy

from ..server.media.input import validate_input_path

from ..preferences import addon_preferences
from ..properties import (
    ai_ready,
    ai_setup_label,
    ai_status,
    model_ready,
    model_record,
)
from ..runtime import runtime


def draw_ai_setup(layout):
    status = ai_status()
    if not status["ready"]:
        layout.operator(
            "anyimage.setup_ai_environment",
            text=ai_setup_label(status),
            icon="IMPORT",
        )
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
    if not runtime.environment_ready():
        raise RuntimeError("Install the AnyImage Environment first")


def invoke_ai_setup_if_needed(operator):
    if ai_ready():
        return None
    try:
        return bpy.ops.anyimage.setup_ai_environment("INVOKE_DEFAULT")
    except RuntimeError as error:
        report_ai_error(operator, error)
        return {"CANCELLED"}


def require_model(model_key):
    model = model_record(model_key)
    if model is None:
        raise RuntimeError(f"Unknown model: {model_key}")
    if not model_ready(model_key):
        raise RuntimeError(f"Download {model['label']} first")
    return model


def moge2_parameters(path, model, resolution_level):
    return {
        "input": str(path),
        "model": model,
        "resolution_level": int(resolution_level),
        "device": production_device().lower(),
    }
