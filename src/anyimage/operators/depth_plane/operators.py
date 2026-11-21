"""Submit and apply geometry jobs shared by depth and relief conversion."""

import bpy

from ...common.ai import (
    geometry_job_parameters,
    invoke_ai_setup_if_needed,
    report_ai_error,
)
from ...common.color_image import require_static_color_image
from ...common.image import image_content_signature, image_pixels, image_rgba, is_image_empty, require_image_empty
from ...common.image_input import cleanup_image_input
from ...common.job_image import prepare_recognition_input
from ...runtime import JobOperator
from .object import create_depth_plane_from_result

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class GeneratePlaneGeometry(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.generate_plane_geometry"
    bl_label = "Generate Plane Geometry"
    job_type = "generate_depth_plane_geometry"
    starting_message = "Preparing depth conversion"

    _input_path = None
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    plane_type: bpy.props.EnumProperty(
        items=(("DEPTH", "Depth Plane", ""), ("RELIEF", "Relief", "")),
        default="DEPTH", options=_HIDDEN,
    )

    def request(self, context):
        parameters = geometry_job_parameters(context)
        self._source_object = require_image_empty(self.source_object_name)
        image = self._source_image = self._source_object.data
        pixels = image_pixels(image)
        self._source_signature = image_content_signature(image, pixels)
        self._input_path = prepare_recognition_input(image, image_rgba(image, pixels))
        return {
            **parameters,
            "input": str(self._input_path),
            "plane_type": self.plane_type,
        }

    def response(self, context, result):
        label = (
            ConvertToReliefPlane.bl_label if self.plane_type == "RELIEF"
            else ConvertToDepthPlane.bl_label
        )
        create_depth_plane_from_result(
            context, result, self, plane_type=self.plane_type, undo_label=label,
        )
        return "Relief is ready" if self.plane_type == "RELIEF" else "Depth Plane is ready"

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._source_object = self._source_image = self._source_signature = None


def start_depth_conversion(operator, context, plane_type):
    source_object = context.object
    try:
        require_static_color_image(source_object.data)
    except ValueError as error:
        operator.report({"ERROR"}, str(error))
        return {"CANCELLED"}
    setup_result = invoke_ai_setup_if_needed(operator)
    if setup_result is not None:
        return setup_result
    try:
        result = bpy.ops.anyimage.generate_plane_geometry(
            plane_type=plane_type,
            source_object_name=source_object.name,
        )
    except (OSError, RuntimeError, ValueError) as error:
        report_ai_error(operator, error)
        return {"CANCELLED"}
    return {"CANCELLED"} if "CANCELLED" in result else {"FINISHED"}


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
        from ...runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        return start_depth_conversion(self, context, "DEPTH")


class ConvertToReliefPlane(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_relief_plane"
    bl_label = "Convert to Relief"
    bl_description = "Use AI-estimated depth to create a raised relief on a flat base."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        return start_depth_conversion(self, context, "RELIEF")
