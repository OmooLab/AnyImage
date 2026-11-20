import bpy
from .properties import (
    COLOR_REFERENCE_PALETTE_PROPERTIES,
    COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES,
)


class ColorMatchPanel(bpy.types.Panel):
    bl_label = "Color Match"
    bl_idname = "ANYIMAGE_PT_color_match"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Any Image"
    bl_order = 10

    def draw(self, context):
        settings = context.scene.anyimage_settings
        self.layout.template_icon_view(
            settings,
            "color_reference_choice",
            show_labels=False,
            scale=6.0,
            scale_popup=5.0,
        )
        row = self.layout.row(align=True)
        weights = [
            getattr(settings, name) ** 0.5
            for name in COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES[:settings.color_reference_palette_count]
        ] or [1.0]
        total = sum(weights) or 1.0
        for name, weight in zip(COLOR_REFERENCE_PALETTE_PROPERTIES, weights):
            cell = row.row(align=True)
            cell.scale_x = max(weight / total * len(weights), 0.1)
            cell.prop(settings, name, text="")
