"""Convert an Image Empty into a raised relief."""

import bpy

from ..common.image import is_image_empty
from .plane_geometry import start_depth_conversion


class ConvertToReliefPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_relief_plane"
    bl_label = "Convert to Relief"
    bl_description = "Use AI-estimated depth to create a raised relief on a flat base."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        return start_depth_conversion(self, context, "RELIEF")
