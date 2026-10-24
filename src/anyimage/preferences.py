import bpy

DEFAULT_MAX_FRAME_RESOLUTION = 2048
MIN_FRAME_RESOLUTION = 64
MAX_FRAME_RESOLUTION = 8192
DEFAULT_CUTOUT_BOUNDARY_PADDING = 2.0
MIN_CUTOUT_BOUNDARY_PADDING = 1.0
MAX_CUTOUT_BOUNDARY_PADDING = 4.0
ADDON_PACKAGE = __package__
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


def configured_material_view_adaptation(context=None):
    return bool(getattr(addon_preferences(context), "adapt_material_to_view_transform", True))


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


class AnyImagePreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_PACKAGE

    adapt_material_to_view_transform: bpy.props.BoolProperty(
        name="Compensate Image Colors",
        description=(
            "Compensate for the scene's view transform when creating materials "
            "to keep colors close to the source image. "
            "To view materials, switch the viewport to Material Preview or Rendered mode."
        ),
        default=True,
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
        description="Sample inward and extend Cutout image data at the outline",
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

    @staticmethod
    def _draw_box(layout, label):
        box = layout.box()
        box.label(text=label)
        return box

    def draw(self, _context):
        layout = self.layout
        shading = self._draw_box(layout, "Shading")
        shading.prop(self, "adapt_material_to_view_transform")
        tools = self._draw_box(layout, "Tools")
        tools.label(text="Frame Tool")
        tools.prop(self, "max_frame_resolution")
        tools.separator(type="LINE")
        tools.label(text="Cutout Tool")
        tools.prop(self, "min_cutout_relative_edge_length")
        tools.prop(self, "cutout_boundary_padding")
        tools.prop(self, "balloon_profile_algorithm")
