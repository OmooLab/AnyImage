"""Submit and apply geometry jobs shared by depth and relief conversion."""

import bpy

from ...ai_preferences import configured_max_ai_input_size

from ...common.ai import geometry_job_parameters, invoke_ai_setup_if_needed
from ...common.color_image import require_static_color_image
from ...common.image import image_content_signature, image_pixels, image_rgba, is_image_empty
from ...common.image_input import cleanup_image_input, prepare_moge_input
from ...runtime import JobOperator
from .object import create_depth_plane_from_result


class DepthPlaneJob(JobOperator):
    bl_options = {"REGISTER"}
    job_type = "generate_depth_plane_geometry"
    starting_message = "Preparing depth conversion"
    _input_path = None

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        source = context.object
        try:
            require_static_color_image(source.data)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        setup = invoke_ai_setup_if_needed(self)
        if setup is not None:
            return setup
        self._source_object = source
        self._source_image = source.data
        return super().execute(context)

    def request(self, context):
        parameters = geometry_job_parameters(context)
        image = self._source_image
        pixels = image_pixels(image)
        self._source_signature = image_content_signature(image, pixels)
        self._input_path = prepare_moge_input(
            image, image_rgba(image, pixels), max_input_size=configured_max_ai_input_size(context),
        )
        return {
            **parameters,
            "input": str(self._input_path),
            "output_size": tuple(image.size),
            "plane_type": self.plane_type,
        }

    def response(self, context, result):
        create_depth_plane_from_result(context, result, self)
        return self.ready_message

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._source_object = self._source_image = self._source_signature = None


class ConvertToDepthPlane(DepthPlaneJob, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_depth_plane"
    bl_label = "Convert to Depth Plane"
    bl_description = (
        "Use AI-estimated depth to turn the image into a 3D surface "
        "that follows the source image's perspective."
    )
    plane_type = "DEPTH"
    ready_message = "Depth Plane is ready"


class ConvertToReliefPlane(DepthPlaneJob, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_relief_plane"
    bl_label = "Convert to Relief"
    bl_description = "Use AI-estimated depth to create a raised relief on a flat base."
    plane_type = "RELIEF"
    ready_message = "Relief is ready"
