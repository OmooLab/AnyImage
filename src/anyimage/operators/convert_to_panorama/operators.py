"""Submit the current static panorama through the managed geometry Job."""

import bpy

from ...ai_preferences import configured_geometry_model, configured_max_ai_input_size
from ...common.ai import (
    geometry_job_parameters, invoke_ai_setup_if_needed, report_ai_error, require_environment, require_model,
)
from ...common.image import (
    image_content_signature, image_pixels, image_rgba, is_animated_image, is_image_empty, require_image_empty,
)
from ...common.image_input import cleanup_image_input
from ...common.job_image import prepare_recognition_input
from ...common.panorama import panorama_crop_bounds, report_panorama_crop
from ...preferences import addon_preferences
from ...server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ...runtime import JobOperator
from ...server.media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, MAX_MAX_AI_INPUT_SIZE, MIN_MAX_AI_INPUT_SIZE
from .object import create_panorama_from_result

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class GeneratePanorama(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.generate_panorama"
    bl_label = "Generate Panorama"
    job_type = "generate_panorama_geometry"
    starting_message = "Preparing panorama conversion"

    _input_path = None
    crop_bounds: bpy.props.IntVectorProperty(size=4, options=_HIDDEN)
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    model: bpy.props.StringProperty(default=DEFAULT_GEOMETRY_MODEL_KEY, options=_HIDDEN)
    resolution_level: bpy.props.IntProperty(default=3, min=0, max=9, options=_HIDDEN)
    max_input_size: bpy.props.IntProperty(default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE, max=MAX_MAX_AI_INPUT_SIZE, options=_HIDDEN)

    def request(self, context):
        require_environment()
        require_model(self.model)
        self._source_object = require_image_empty(self.source_object_name)
        image = self._source_image = self._source_object.data
        pixels = image_pixels(image)
        self._source_signature = image_content_signature(image, pixels)
        left, top, right, bottom = self.crop_bounds
        cropped = image_rgba(image, pixels)[top:bottom, left:right]
        self._input_path = prepare_recognition_input(image, cropped)
        return {
            **geometry_job_parameters(self._input_path, self.model, self.resolution_level),
            "max_input_size": int(self.max_input_size),
        }

    def response(self, context, result):
        create_panorama_from_result(context, result, self)
        return "Panorama is ready"

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._source_object = self._source_image = self._source_signature = None


class ConvertToPanorama(bpy.types.Operator):
    bl_idname = "anyimage.convert_to_panorama"
    bl_label = "Convert to Panorama"
    bl_description = "Turn a still panoramic image into a surrounding 3D surface using AI-estimated depth."
    bl_options = {"REGISTER", "UNDO"}

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
        try:
            preferences = addon_preferences(context)
            result = bpy.ops.anyimage.generate_panorama(
                source_object_name=source.name, crop_bounds=bounds,
                model=configured_geometry_model(context),
                resolution_level=int(getattr(preferences, "geometry_resolution_level", 3)),
                max_input_size=configured_max_ai_input_size(context),
            )
        except (OSError, RuntimeError, ValueError) as error:
            report_ai_error(self, error)
            return {"CANCELLED"}
        return {"CANCELLED"} if "CANCELLED" in result else {"FINISHED"}
