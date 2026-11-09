"""AI-only Scene properties extending the Lite edition."""

import bpy

from .properties import SettingsLite


class Settings(SettingsLite):
    cutout_generate_normal: bpy.props.BoolProperty(
        name="Normal Map",
        description=(
            "Generate a normal map to add surface detail under lighting for Flat and Solid shapes. "
            "Depth Solid and Depth Symmetry always generate normal maps."
        ),
        default=False,
    )
