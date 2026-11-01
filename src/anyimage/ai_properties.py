"""AI-only Scene properties extending the base edition."""

import bpy

from .properties import AnyImageSettings as SharedSettings


class AnyImageSettings(SharedSettings):
    cutout_generate_normal: bpy.props.BoolProperty(
        name="Normal Map",
        description=(
            "Generate a normal map to add surface detail under lighting for Flat and Solid shapes. "
            "Depth Solid and Depth Symmetry always generate normal maps."
        ),
        default=False,
    )
