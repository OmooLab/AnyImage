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

DEFAULT_MAX_FRAME_RESOLUTION = 2048
MIN_FRAME_RESOLUTION = 64
MAX_FRAME_RESOLUTION = 8192
DEFAULT_CUTOUT_BOUNDARY_PADDING = 2.0
MIN_CUTOUT_BOUNDARY_PADDING = 1.0
MAX_CUTOUT_BOUNDARY_PADDING = 4.0

ADDON_PACKAGE = __package__
DEFAULT_STORAGE_ROOT = Path.home() / ".anyimage"
UPSCALE_MODEL_ITEMS = tuple(
    (model.key, f"{tier} | {model.label}", model.description, number)
    for model, tier, number in zip(UPSCALE_MODELS.values(), ("Fast", "Base", "Pro"), (0, 2, 4))
)

BACKGROUND_MODEL_ITEMS = tuple(
    (model.key, f"{tier} | {model.label}", model.description, number)
    for model, tier, number in zip(BACKGROUND_MODELS.values(), ("Fast", "Base", "Pro"), (1, 0, 2))
)

BALLOON_PROFILE_ALGORITHM_ITEMS = (
    (
        "POISSON",
        "Poisson",
        "Create a smooth, rounded bulge within the Cutout outline.",
    ),
    ("TEDDY", "Teddy", "Create a bulge shaped by the Cutout's central branches."),
)


def addon_preferences(context=None):
    preference_context = (
        context if getattr(context, "preferences", None) is not None else bpy.context
    )
    addon = preference_context.preferences.addons.get(ADDON_PACKAGE)
    return getattr(addon, "preferences", None)


def configured_storage_root():
    configured = getattr(addon_preferences(), "storage_root", "")
    if configured:
        return Path(bpy.path.abspath(configured))
    return DEFAULT_STORAGE_ROOT


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
    return _configured_model(context, "background_model", BACKGROUND_MODELS, DEFAULT_BACKGROUND_MODEL_KEY)


def configured_upscale_model(context=None):
    return _configured_model(context, "upscale_model", UPSCALE_MODELS, DEFAULT_UPSCALE_MODEL_KEY)


def configured_material_view_adaptation(context=None):
    return bool(
        getattr(addon_preferences(context), "adapt_material_to_view_transform", True)
    )


def configured_min_cutout_relative_edge_length(context=None):
    percent = float(getattr(addon_preferences(context), "min_cutout_relative_edge_length", 1.0))
    return min(max(percent, 0.001), 100.0) / 100.0


def configured_cutout_boundary_padding(context=None):
    value = float(
        getattr(
            addon_preferences(context),
            "cutout_boundary_padding",
            DEFAULT_CUTOUT_BOUNDARY_PADDING,
        )
    )
    return min(max(value, MIN_CUTOUT_BOUNDARY_PADDING), MAX_CUTOUT_BOUNDARY_PADDING)


def configured_max_frame_resolution(context=None):
    preferences = addon_preferences(context)
    value = int(
        getattr(
            preferences,
            "max_frame_resolution",
            DEFAULT_MAX_FRAME_RESOLUTION,
        )
    )
    return min(max(value, MIN_FRAME_RESOLUTION), MAX_FRAME_RESOLUTION)


def configured_max_ai_input_size(context=None):
    preferences = addon_preferences(context)
    value = int(getattr(preferences, "max_ai_input_size", DEFAULT_MAX_AI_INPUT_SIZE))
    return min(max(value, MIN_MAX_AI_INPUT_SIZE), MAX_MAX_AI_INPUT_SIZE)


def device_items(owner, context):
    from .properties import device_enum_items

    return device_enum_items(owner, context)


def geometry_model_items(owner, context):
    from .properties import geometry_model_enum_items

    return geometry_model_enum_items(owner, context)


class AnyImagePreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    adapt_material_to_view_transform: bpy.props.BoolProperty(
        name="Preserve Image Colors",
        description=(
            "Compensate for the scene's view transform to keep image colors "
            "close to the original when creating materials."
        ),
        default=True,
    )
    storage_root: bpy.props.StringProperty(
        name="Storage Folder",
        description=(
            "Choose where AnyImage stores its AI environment, downloaded models, and task files."
        ),
        subtype="DIR_PATH",
        default=str(DEFAULT_STORAGE_ROOT),
    )
    device: bpy.props.EnumProperty(
        name="AI Processing Device",
        description=(
            "Choose the CPU or GPU used to run AI models."
        ),
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
    min_cutout_relative_edge_length: bpy.props.FloatProperty(
        name="Minimum Relative Edge Length",
        description="Minimum target edge length as a percentage of the Cutout bounds' longest side",
        default=1.0,
        min=0.001,
        max=100.0,
        soft_min=0.5,
        soft_max=10.0,
        subtype="PERCENTAGE",
    )
    cutout_boundary_padding: bpy.props.FloatProperty(
        name="Boundary Padding",
        description="Sample inward and extend Cutout color and depth at the outline",
        default=DEFAULT_CUTOUT_BOUNDARY_PADDING,
        min=MIN_CUTOUT_BOUNDARY_PADDING,
        max=MAX_CUTOUT_BOUNDARY_PADDING,
        subtype="PIXEL",
    )
    max_frame_resolution: bpy.props.IntProperty(
        name="Maximum Frame Resolution",
        description="Set the maximum length, in pixels, of the combined image's longest edge.",
        default=DEFAULT_MAX_FRAME_RESOLUTION,
        min=MIN_FRAME_RESOLUTION,
        max=MAX_FRAME_RESOLUTION,
        step=128,
        subtype="PIXEL",
    )
    balloon_profile_algorithm: bpy.props.EnumProperty(
        name="Balloon Profile",
        description="Control how the Cutout surface bulges outward from its outline.",
        items=BALLOON_PROFILE_ALGORITHM_ITEMS,
        default="POISSON",
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
        from .properties import ai_setup_label, ai_status, model_catalog
        from .runtime import runtime

        layout = self.layout
        status = ai_status()
        models = {model["key"]: model for model in model_catalog()}

        server = self._draw_box(layout, "Server")
        server.prop(self, "storage_root")
        server_row = server.row(align=True)
        if not status["environment_ready"]:
            setup_row = server_row.row(align=True)
            setup_row.enabled = not runtime.server_busy()
            setup_row.operator(
                "anyimage.setup_ai_environment",
                text=ai_setup_label(status),
                icon="IMPORT",
            )
        else:
            server_row.label(text="Installed", icon="CHECKMARK")
        server_row.operator(
            "anyimage.open_server_log",
            text="Open Server Log",
            icon="TEXT",
        )

        if status["environment_ready"]:
            ai = self._draw_box(layout, "AI")
            ai.prop(self, "device")
            ai.prop(self, "max_ai_input_size")
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

        shading = self._draw_box(layout, "Shading")
        shading.prop(self, "adapt_material_to_view_transform")

        tools = self._draw_box(layout, "Tools")
        tools.label(text="Frame Tool")
        tools.prop(self, "max_frame_resolution")
        tools.separator(type="LINE")
        tools.label(text="Depth & Normal")
        tools.prop(self, "geometry_resolution_level")
        tools.separator(type="LINE")
        tools.label(text="Cutout Tool")
        tools.prop(self, "min_cutout_relative_edge_length")
        tools.prop(self, "cutout_boundary_padding")
        tools.prop(self, "balloon_profile_algorithm")

    @staticmethod
    def _draw_box(layout, label):
        box = layout.box()
        box.label(text=label)
        return box

    def _draw_model_property(
        self,
        layout,
        property_name,
        models,
        default_model_key,
        ready_label,
    ):
        model_key = getattr(self, property_name, default_model_key)
        choices = {"geometry_model": MOGE_MODELS, "background_model": BACKGROUND_MODELS, "upscale_model": UPSCALE_MODELS}
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
        from .runtime import runtime

        row = layout.row(align=True)
        if model is None:
            row.label(text="Unavailable", icon="ERROR")
            return
        if model.get("ready"):
            row.label(text=ready_label, icon="CHECKMARK")
            return
        download_row = row.row(align=True)
        download_row.enabled = not runtime.server_busy()
        operator = download_row.operator(
            "anyimage.download_model",
            text="Download",
            icon="IMPORT",
        )
        operator.model = model["key"]
