import bpy

from ..ai_preferences import configured_max_ai_input_size, configured_upscale_model
from ..server.model_catalog import UPSCALE_MODELS
from ..runtime import JobOperator
from ..common.ai import invoke_ai_setup_if_needed, model_job_parameters
from ..common.job_image import apply_image_result
from ..common.image_input import cleanup_image_input, prepare_input_png
from ..common.image_target import ImageEditTarget, editable_still_image

UPSCALE_FACTOR = 2


def upscale_output_size(image):
    width, height = (int(value) for value in getattr(image, "size", (0, 0)))
    if width <= 0 or height <= 0:
        return None
    return width * UPSCALE_FACTOR, height * UPSCALE_FACTOR


def upscale_input_size_allowed(image, max_input_size):
    width, height = (int(value) for value in getattr(image, "size", (0, 0)))
    if width <= 0 or height <= 0:
        return True
    return max(width, height) < int(max_input_size)


class UpscaleImage(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.upscale_image"
    bl_label = "Upscale"
    bl_description = "Upscale the image by 2x with an AI model"
    bl_options = {"UNDO"}
    job_type = "upscale_image"
    starting_message = "Starting image upscale"

    _input_path = None

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        image = editable_still_image(context)
        return (
            image is not None
            and not image.is_float
            and upscale_input_size_allowed(image, configured_max_ai_input_size(context))
            and runtime.can_submit()
        )

    def invoke(self, context, _event):
        setup_result = invoke_ai_setup_if_needed(self)
        if setup_result is not None:
            return setup_result
        return self.execute(context)

    def request(self, context):
        self._model = configured_upscale_model(context)
        parameters = model_job_parameters(self._model)
        max_input_size = configured_max_ai_input_size(context)
        self._image_target, rgba = ImageEditTarget.capture(context)
        source_image = self._image_target.image
        if source_image.is_float:
            raise ValueError("Upscale requires a non-HDR image")
        if not upscale_input_size_allowed(source_image, max_input_size):
            raise ValueError(bpy.app.translations.pgettext_rpt(
                "Image long edge must be smaller than Maximum AI Input Size ({size} px)"
            ).format(size=max_input_size))
        self._input_path = prepare_input_png(rgba)
        return {
            **parameters,
            "input": str(self._input_path),
            "max_input_size": max_input_size,
        }

    def response(self, _context, result):
        apply_image_result(self._image_target, result.file("upscale"))
        model_label = UPSCALE_MODELS[self._model].label
        return bpy.app.translations.pgettext_iface("Image is upscaled with {model}").format(model=model_label)

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._image_target = None
