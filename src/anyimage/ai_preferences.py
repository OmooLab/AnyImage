from .preferences import (
    ADDON_PACKAGE,
    addon_preferences,
)
from .preferences import AnyImagePreferences as SharedPreferences
from pathlib import Path
import bpy
from .server.media.resolution import (
    DEFAULT_MAX_AI_INPUT_SIZE,
    MAX_MAX_AI_INPUT_SIZE,
    MIN_MAX_AI_INPUT_SIZE,
)
from .server.model_catalog import (
    BACKGROUND_MODELS,
    MOGE_MODELS,
    DEFAULT_BACKGROUND_MODEL_KEY,
    DEFAULT_GEOMETRY_MODEL_KEY,
    DEFAULT_UPSCALE_MODEL_KEY,
    UPSCALE_MODELS,
)

DEFAULT_STORAGE_ROOT = Path.home() / ".anyimage"
UPSCALE_MODEL_ITEMS = tuple(
    (model.key, f"{model.tier} | {model.label}", model.description, model.enum_value)
    for model in UPSCALE_MODELS.values()
)
BACKGROUND_MODEL_ITEMS = tuple(
    (model.key, f"{model.tier} | {model.label}", model.description, model.enum_value)
    for model in BACKGROUND_MODELS.values()
)


def storage_root(path=None):
    """Read the Server location or persist a new one in Blender preferences."""
    preferences = addon_preferences()
    if path is not None:
        previous = preferences.storage_root
        preferences.storage_root = str(path)
        try:
            if "FINISHED" not in bpy.ops.wm.save_userpref():
                raise RuntimeError("Unable to save the Server location")
        except Exception:
            preferences.storage_root = previous
            raise
    configured = getattr(preferences, "storage_root", "")
    return Path(bpy.path.abspath(configured)) if configured else DEFAULT_STORAGE_ROOT


def _configured_model(context, property_name, models, default):
    preferences = addon_preferences(context)
    model = getattr(preferences, property_name, default)
    if model not in models:
        setattr(preferences, property_name, default)
        return default
    return model


def configured_geometry_model(context=None):
    return _configured_model(context, "geometry_model", MOGE_MODELS, DEFAULT_GEOMETRY_MODEL_KEY)


def configured_background_model(context=None):
    return _configured_model(
        context, "background_model", BACKGROUND_MODELS, DEFAULT_BACKGROUND_MODEL_KEY
    )


def configured_upscale_model(context=None):
    return _configured_model(context, "upscale_model", UPSCALE_MODELS, DEFAULT_UPSCALE_MODEL_KEY)


def configured_panorama_light_probe(context=None):
    preferences = addon_preferences(context)
    return (
        bool(getattr(preferences, "panorama_light_probe_enabled", True)),
        max(0.5, float(getattr(preferences, "panorama_light_probe_max_distance", 20.0))),
    )


def configured_max_ai_input_size(context=None):
    preferences = addon_preferences(context)
    value = int(getattr(preferences, "max_ai_input_size", DEFAULT_MAX_AI_INPUT_SIZE))
    return min(max(value, MIN_MAX_AI_INPUT_SIZE), MAX_MAX_AI_INPUT_SIZE)


def device_items(owner, context):
    from .ai_properties import device_enum_items

    return device_enum_items(owner, context)


def geometry_model_items(owner, context):
    from .ai_properties import geometry_model_enum_items

    return geometry_model_enum_items(owner, context)


class AnyImagePreferences(SharedPreferences):
    bl_idname = ADDON_PACKAGE

    panorama_light_probe_enabled: bpy.props.BoolProperty(
        name="Panorama Light Probe",
        default=True,
        description="Create and bake a light probe volume from the panorama",
    )

    panorama_light_probe_max_distance: bpy.props.FloatProperty(
        name="Maximum Distance per Direction (m)",
        default=20.0,
        min=0.5,
        description="Maximum distance from the panorama origin in each direction, in meters",
    )

    storage_root: bpy.props.StringProperty(
        name="Server Root Folder",
        description=(
            "Choose where AnyImage stores its AI environment, downloaded models, and task files."
        ),
        subtype="DIR_PATH",
        options={"HIDDEN"},
        default=str(DEFAULT_STORAGE_ROOT),
    )

    device: bpy.props.EnumProperty(
        name="AI Processing Device",
        description=("Choose the CPU or GPU used to run AI models."),
        items=device_items,
        default=0,
    )

    upscale_model: bpy.props.EnumProperty(
        name="Upscale Image Model",
        description="Model used to upscale images",
        items=UPSCALE_MODEL_ITEMS,
        default=DEFAULT_UPSCALE_MODEL_KEY,
    )

    max_ai_input_size: bpy.props.IntProperty(
        name="Maximum AI Input Size",
        description=(
            "Limit the longest image edge used for depth, normal, and selection refinement. "
            "Upscale requires a source image smaller than this limit."
        ),
        default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE,
        max=MAX_MAX_AI_INPUT_SIZE,
        step=256,
        subtype="PIXEL",
    )

    background_model: bpy.props.EnumProperty(
        name="Remove Background Model",
        description="Model used to remove image backgrounds",
        items=BACKGROUND_MODEL_ITEMS,
        default=DEFAULT_BACKGROUND_MODEL_KEY,
    )

    geometry_model: bpy.props.EnumProperty(
        name="Depth & Normal Model",
        description="Choose the AI model used to generate depth and surface normals.",
        items=geometry_model_items,
        default=0,
    )

    geometry_resolution_level: bpy.props.IntProperty(
        name="MoGe Resolution Level",
        description=(
            "Set the processing resolution for depth and normal generation. "
            "Higher levels can capture finer details but take more time and memory."
        ),
        default=5,
        min=0,
        max=9,
    )

    def draw(self, _context):
        from .operators.ai_setup import SetupAIServer
        from .ai_properties import ai_setup_label, ai_status, model_catalog
        from .runtime import runtime

        layout = self.layout
        status = ai_status()
        models = {model["key"]: model for model in model_catalog()}

        server = self._draw_box(layout, "AI Server")
        location_row = server.row(align=True)
        location_row.label(text=str(storage_root()), icon="FILE_FOLDER")
        if not status["environment_ready"]:
            setup_row = server.row(align=True)
            setup_row.enabled = not runtime.server_busy()
            setup_row.operator(
                SetupAIServer.bl_idname,
                text=ai_setup_label(status),
                icon="IMPORT",
            )
        else:
            migrate_row = location_row.row(align=True)
            migrate_row.enabled = not runtime.server_busy()
            migrate_row.operator("anyimage.migrate_server", icon="FILE_FOLDER")
            server.label(text="Installed", icon="CHECKMARK")

        if status["environment_ready"]:
            ai = self._draw_box(layout, "AI")
            ai.prop(self, "device")
            ai.prop(self, "max_ai_input_size")
            ai.prop(self, "geometry_resolution_level")
            ai.separator(type="LINE")
            self._draw_model_property(
                ai,
                "geometry_model",
                models,
                DEFAULT_GEOMETRY_MODEL_KEY,
                "AI Generate Depth Map",
            )
            self._draw_model_property(
                ai,
                "background_model",
                models,
                DEFAULT_BACKGROUND_MODEL_KEY,
                "AI Remove Background",
            )
            self._draw_model_property(
                ai,
                "upscale_model",
                models,
                DEFAULT_UPSCALE_MODEL_KEY,
                "AI Upscale Image",
            )

        super().draw(_context)
        panorama = self._draw_box(layout, "Panorama")
        panorama.prop(self, "panorama_light_probe_enabled")
        probe = panorama.row()
        probe.enabled = getattr(self, "panorama_light_probe_enabled", True)
        probe.prop(self, "panorama_light_probe_max_distance")

    def _draw_model_property(
        self,
        layout,
        property_name,
        models,
        default_model_key,
        ready_label,
    ):
        model_key = getattr(self, property_name, default_model_key)
        choices = {
            "geometry_model": MOGE_MODELS,
            "background_model": BACKGROUND_MODELS,
            "upscale_model": UPSCALE_MODELS,
        }
        if model_key not in choices[property_name]:
            model_key = default_model_key
            setattr(self, property_name, model_key)
        split = layout.split(factor=0.58, align=True)
        split.column(align=True).prop(self, property_name, text="")
        self._draw_model_status(
            split.column(align=True),
            models.get(model_key),
            ready_label,
        )

    @staticmethod
    def _draw_model_status(layout, model, ready_label):
        from .operators.ai_setup import DownloadModel
        from .runtime import runtime

        row = layout.row(align=True)
        if model is None:
            row.label(text="Unavailable", icon="ERROR")
            return
        error = model.get("validation_error")
        if error:
            row.label(text="Validation failed", icon="ERROR")
        elif model.get("installed"):
            row.label(
                text=bpy.app.translations.pgettext_iface("{label} (Installed)").format(
                    label=bpy.app.translations.pgettext_iface(ready_label),
                ),
                translate=False,
                icon="CHECKMARK",
            )
            return
        download_row = row.row(align=True)
        download_row.enabled = not runtime.server_busy()
        operator = download_row.operator(
            DownloadModel.bl_idname,
            text="Download Again" if error else "Download",
            icon="IMPORT",
        )
        operator.model = model["key"]
