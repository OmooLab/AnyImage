"""Submit the current static panorama through the managed geometry Job."""

import bpy

from ...ai_preferences import configured_max_ai_input_size
from ...common.ai import geometry_job_parameters, invoke_ai_setup_if_needed
from ...common.image import (
    image_content_signature, image_pixels, image_rgba, is_animated_image, is_image_empty,
)
from ...common.image_input import cleanup_image_input, prepare_moge_input
from ...common.panorama import panorama_crop_bounds, report_panorama_crop
from ...runtime import JobOperator
from .object import create_panorama_from_result


class ConvertToPanorama(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.convert_to_panorama"
    bl_label = "Convert to Panorama"
    bl_description = "Turn a still panoramic image into a surrounding 3D surface using AI-estimated depth."
    bl_options = {"REGISTER"}

    job_type = "generate_panorama_geometry"
    starting_message = "Preparing panorama conversion"
    _input_path = None

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return is_image_empty(context.object) and runtime.can_submit()

    def execute(self, context):
        source = context.object
        image = source.data
        width, height = image.size
        if is_animated_image(image):
            self.report({"ERROR"}, "Panorama conversion requires a static image")
            return {"CANCELLED"}
        try:
            bounds = panorama_crop_bounds(width, height)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        setup = invoke_ai_setup_if_needed(self)
        if setup is not None:
            return setup
        report_panorama_crop(self, image.size, bounds)
        self._source_object = source
        self._source_image = image
        self.crop_bounds = bounds
        return super().execute(context)

    def request(self, context):
        parameters = geometry_job_parameters(context)
        image = self._source_image
        pixels = image_pixels(image)
        self._source_signature = image_content_signature(image, pixels)
        left, top, right, bottom = self.crop_bounds
        cropped = image_rgba(image, pixels)[top:bottom, left:right]
        self._input_path = prepare_moge_input(
            image, cropped, max_input_size=configured_max_ai_input_size(context), panorama=True,
        )
        return {
            **parameters,
            "input": str(self._input_path),
        }

    def response(self, context, result):
        create_panorama_from_result(context, result, self)
        return "Panorama is ready"

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._source_object = self._source_image = self._source_signature = None
