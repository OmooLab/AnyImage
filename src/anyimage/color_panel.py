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
    bl_category = "AnyImage"
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
        palette_count = min(
            settings.color_reference_palette_count,
            len(COLOR_REFERENCE_PALETTE_PROPERTIES),
        )
        count = palette_count or 1
        display_weights = [
            max(getattr(settings, COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES[index]), 0.0) ** 0.5
            if palette_count
            else 1.0
            for index in range(count)
        ]
        display_total = sum(display_weights) or 1.0
        for index in range(count):
            cell = row.row(align=True)
            cell.scale_x = max(display_weights[index] / display_total * count, 0.1)
            cell.prop(settings, COLOR_REFERENCE_PALETTE_PROPERTIES[index], text="")
