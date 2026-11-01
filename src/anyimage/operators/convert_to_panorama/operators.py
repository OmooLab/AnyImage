"""Submit the current static panorama through the managed geometry Job."""

import bpy

from ...common.ai import geometry_job_parameters, invoke_ai_setup_if_needed, report_ai_error, require_environment, require_input_path, require_model
from ...common.job_image import material_analysis_input
from ...common.image import is_image_empty, is_animated_image, require_image_empty, image_content_signature
from ...common.color_image import prepare_material_color_input, cleanup_material_color_input
from ...preferences import addon_preferences
from ...ai_preferences import configured_max_ai_input_size
from ...ai_preferences import configured_geometry_model
from ...server.model_catalog import DEFAULT_GEOMETRY_MODEL_KEY
from ...runtime import JobOperator
from ...server.media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, MAX_MAX_AI_INPUT_SIZE, MIN_MAX_AI_INPUT_SIZE
from .object import create_panorama_from_result

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


def panorama_crop_bounds(width, height):
    """Return the largest centered integer-pixel 2:1 bounds."""
    width, height = int(width), int(height)
    crop_height = min(height, width // 2)
    crop_width = crop_height * 2
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("Panorama conversion requires an image at least 2 x 1 pixels")
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return left, top, left + crop_width, top + crop_height


class GeneratePanorama(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.generate_panorama"
    bl_label = "Generate Panorama"
    job_type = "generate_panorama_geometry"
    starting_message = "Preparing panorama conversion"

    input_path: bpy.props.StringProperty(options=_HIDDEN)
    color_path: bpy.props.StringProperty(options=_HIDDEN)
    source_object_name: bpy.props.StringProperty(options=_HIDDEN)
    model: bpy.props.StringProperty(default=DEFAULT_GEOMETRY_MODEL_KEY, options=_HIDDEN)
    resolution_level: bpy.props.IntProperty(default=5, min=0, max=9, options=_HIDDEN)
    max_input_size: bpy.props.IntProperty(default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE, max=MAX_MAX_AI_INPUT_SIZE, options=_HIDDEN)

    def execute(self, context):
        try:
            self._source_object = require_image_empty(self.source_object_name)
            self._source_image = self._source_object.data
            self._source_signature = image_content_signature(self._source_image)
        except RuntimeError as error:
            cleanup_material_color_input(self.color_path)
            report_ai_error(self, error)
            return {"CANCELLED"}
        return super().execute(context)

    def request(self, context):
        require_environment()
        require_model(self.model)
        return {
            **geometry_job_parameters(require_input_path(self.input_path), self.model, self.resolution_level),
            "max_input_size": int(self.max_input_size),
        }

    def response(self, context, result):
        create_panorama_from_result(context, result, self)
        return "Panorama is ready"

    def cleanup(self):
        cleanup_material_color_input(self.color_path)
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
        crop_width = bounds[2] - bounds[0]
        crop_height = bounds[3] - bounds[1]
        if (crop_width, crop_height) != (width, height):
            self.report({"WARNING"}, bpy.app.translations.pgettext_rpt(
                "Panorama input cropped from {width} x {height} to {crop_width} x {crop_height}"
            ).format(width=width, height=height, crop_width=crop_width, crop_height=crop_height))
        color_path = None
        try:
            preferences = addon_preferences(context)
            color_path = prepare_material_color_input(image, bounds)
            path = material_analysis_input(color_path)
            result = bpy.ops.anyimage.generate_panorama(
                input_path=str(path), color_path=str(color_path), source_object_name=source.name,
                model=configured_geometry_model(context),
                resolution_level=int(getattr(preferences, "geometry_resolution_level", 5)),
                max_input_size=configured_max_ai_input_size(context),
            )
        except (OSError, RuntimeError, ValueError) as error:
            cleanup_material_color_input(color_path)
            report_ai_error(self, error)
            return {"CANCELLED"}
        if "CANCELLED" in result:
            cleanup_material_color_input(color_path)
            return {"CANCELLED"}
        return {"FINISHED"}
