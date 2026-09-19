import platform
import sys

import bpy

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
    devices = runtime.environment_manifest().get("devices")
    if isinstance(devices, list) and devices:
        names = [
            name
            for device in devices
            if (name := str(device).lower()) in DEVICE_LABELS
        ]
        if not supports_coreml():
            names = [name for name in names if name != "coreml"]
        elif "cpu" in names:
            names = ["cpu", *(name for name in names if name != "cpu")]
        return names or ["cpu"]
    if sys.platform == "win32":
        return ["directml", "cpu"]
    return ["cpu", "coreml"] if supports_coreml() else ["cpu"]


def device_enum_items(_owner, _context):
    return [
        (name.upper(), *DEVICE_LABELS[name], index)
        for index, name in enumerate(supported_devices())
    ]


def models_status(refresh=False):
    status = runtime.server_status().get("resources", {}).get("model_manager", {})
    return {
        "catalog": tuple(
            shared_model_catalog.model_record(
                model,
                _model_files_ready(model),
            )
            for model in shared_model_catalog.DOWNLOADABLE_MODELS.values()
        ),
        "loaded": status.get("loaded", {}),
    }


def _model_files_ready(model):
    directory = runtime.storage_root() / "models" / model.directory_name
    return all(any(directory.glob(pattern)) for pattern in model.ready_patterns)


def model_ready(model_key):
    return any(
        model.get("key") == model_key and model.get("ready")
        for model in models_status().get("catalog", ())
    )


def ai_status():
    environment_ready = runtime.environment_ready()
    ready_models = {model["key"] for model in model_catalog() if model.get("ready")}
    missing_models = tuple(
        model_key for model_key in shared_model_catalog.DEFAULT_MODEL_KEYS if model_key not in ready_models
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
    return (
        "Download Required Models…"
        if status["environment_ready"]
        else "Set Up AI Server…"
    )


def model_download_size(model_key):
    model = shared_model_catalog.get_downloadable_model(model_key)
    return sum(size for _path, size, _checksum in model.r2_files)


def model_catalog():
    return models_status().get("catalog", ())


def model_record(model_key):
    return next(
        (model for model in model_catalog() if model.get("key") == model_key),
        None,
    )


def _model_items(models):
    numbers = {"MOGE2_VITS_NORMAL": 0, "MOGE2_VITB_NORMAL": 1, "MOGE3_VITL": 3}
    return [
        (
            model["key"],
            f"{tier} | {model['label']}",
            f"{model['description']}; license: {model['license']}",
            numbers[model["key"]],
        )
        for model, tier in zip(models, ("Fast", "Base", "Pro"))
    ]


def geometry_model_enum_items(_owner, _context):
    models = [model for model in model_catalog() if model.get("family") == "moge"]
    return _model_items(models)


def upscale_model_label(model_key):
    model = shared_model_catalog.UPSCALE_MODELS.get(model_key)
    return model.label if model is not None else model_key


def cutout_gesture_property():
    return bpy.props.EnumProperty(
        name="Gesture",
        description="Shape used to select the Cutout area",
        items=(
            ("LASSO", "Lasso", "Draw a closed freehand area"),
            ("POLYLINE", "Polyline", "Click points to define a closed area"),
        ),
        default="LASSO",
    )


def mask_gesture_property():
    return bpy.props.EnumProperty(
        name="Gesture",
        description="Shape used to edit image Alpha",
        items=(
            ("LASSO", "Lasso", "Draw a closed freehand area"),
            ("BRUSH", "Brush", "Paint with a circular brush"),
            ("POLYLINE", "Polyline", "Click points to define a closed area"),
        ),
        default="LASSO",
    )


def mask_mode_property():
    return bpy.props.EnumProperty(
        name="Mode",
        description="Choose how the selected or painted area changes image visibility.",
        items=(
            (
                "SET",
                "Set",
                "Keep visible content inside the selected or painted area and hide everything outside.",
                "SELECT_SET",
                0,
            ),
            (
                "EXTEND",
                "Extend",
                "Reveal the selected or painted area while keeping other areas unchanged.",
                "SELECT_EXTEND",
                1,
            ),
            (
                "SUBTRACT",
                "Subtract",
                "Hide the selected or painted area while keeping other areas unchanged.",
                "SELECT_SUBTRACT",
                2,
            ),
        ),
        default="SET",
    )


def mask_radius_property():
    return bpy.props.IntProperty(
        name="Radius",
        description="Brush radius in Viewport pixels",
        default=25,
        min=1,
        soft_max=500,
        subtype="PIXEL",
    )


def cutout_generate_normal_property():
    return bpy.props.BoolProperty(
        name="Normal Map",
        description=(
            "Generate a normal map to add surface detail under lighting for Flat and Solid shapes. "
            "Depth Solid and Depth Symmetry always generate normal maps."
        ),
        default=False,
    )


def cutout_alpha_threshold_property():
    return bpy.props.FloatProperty(
        name="Alpha Threshold",
        description=(
            "Exclude areas below this opacity from the Cutout outline. "
            "Higher values exclude more semi-transparent edges."
        ),
        default=0.9,
        min=0.0,
        max=1.0,
        soft_min=0.1,
        soft_max=0.9,
        subtype="FACTOR",
    )


def cutout_fine_outline_property():
    return bpy.props.BoolProperty(
        name="Fine Outline",
        description="Preserve detailed outlines and meaningful holes; disable to fill holes and simplify outlines",
        default=False,
    )


def _cutout_length_scale(owner):
    scene = getattr(owner, "id_data", None)
    if not isinstance(scene, bpy.types.Scene):
        scene = bpy.context.scene
    return scene.unit_settings.scale_length


def _get_cutout_edge_length(owner):
    return owner.get("cutout_edge_length_meters", 0.1) / _cutout_length_scale(owner)


def _set_cutout_edge_length(owner, value):
    owner["cutout_edge_length_meters"] = value * _cutout_length_scale(owner)


def cutout_edge_length_property(*, store_meters=False, **options):
    if store_meters:
        options.update(get=_get_cutout_edge_length, set=_set_cutout_edge_length)
    return bpy.props.FloatProperty(
        name="Edge Length",
        description="Target mesh edge length in world space",
        default=0.1,
        min=1e-6,
        soft_min=0.01,
        soft_max=1.0,
        unit="LENGTH",
        subtype="DISTANCE",
        **options,
    )


class AnyImageSettings(bpy.types.PropertyGroup):
    cutout_gesture: cutout_gesture_property()
    cutout_alpha_threshold: cutout_alpha_threshold_property()
    cutout_edge_length: cutout_edge_length_property(store_meters=True)
    cutout_fine_outline: cutout_fine_outline_property()
    cutout_generate_normal: cutout_generate_normal_property()
    mask_gesture: mask_gesture_property()
    mask_mode: mask_mode_property()
    mask_radius: mask_radius_property()
