"""Convert an Image Empty into a perspective depth surface."""

import bpy

from ..common.image import is_image_empty
from .plane_geometry import start_depth_conversion


class ConvertToDepthPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_depth_plane"
    bl_label = "Convert to Depth Plane"
    bl_description = (
        "Use AI-estimated depth to turn the image into a 3D surface "
        "that follows the source image's perspective."
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        return start_depth_conversion(self, context, "DEPTH")
