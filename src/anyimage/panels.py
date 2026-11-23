import bpy

from .common.color_reference import get_color_reference
from .common.image import is_static_image


class ColorMatchPanel(bpy.types.Panel):
    bl_label = "Color Match"
    bl_idname = "ANYIMAGE_PT_color_match"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Any Image"
    bl_order = 10

    def draw(self, context):
        image = context.scene.anyimage_settings.color_reference
        if not is_static_image(image):
            self.layout.label(text="No color reference")
            return
        self.layout.label(text=image.name, translate=False)
        try:
            reference = get_color_reference(image)
        except (RuntimeError, ValueError):
            return
        self.layout.template_icon(icon_value=reference.icon_id, scale=6.0)
        if reference.transfer is not None:
            row = self.layout.row(align=True)
            weights = reference.transfer.weights ** 0.5
            total = weights.sum()
            for index, weight in enumerate(weights):
                cell = row.row(align=True)
                cell.scale_x = max(weight / total * len(weights), 0.1)
                cell.prop(context.scene.anyimage_settings, f"reference_swatch_{index}", text="")
