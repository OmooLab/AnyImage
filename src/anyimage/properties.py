import bpy
from .common.color_reference import release_unused_references


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


class SettingsLite(bpy.types.PropertyGroup):
    color_reference: bpy.props.PointerProperty(
        name="Reference",
        type=bpy.types.Image,
        update=release_unused_references,
    )
    cutout_gesture: cutout_gesture_property()
    cutout_alpha_threshold: cutout_alpha_threshold_property()
    cutout_edge_length: cutout_edge_length_property(store_meters=True)
    cutout_fine_outline: cutout_fine_outline_property()
    mask_gesture: mask_gesture_property()
    mask_mode: mask_mode_property()
    mask_radius: mask_radius_property()
