import bpy

from ..preferences import configured_max_ai_input_size
from ..preferences import configured_upscale_model
from ..properties import upscale_model_label
from ..server.media.resolution import (
    DEFAULT_MAX_AI_INPUT_SIZE,
    MAX_MAX_AI_INPUT_SIZE,
    MIN_MAX_AI_INPUT_SIZE,
)
from ..runtime import JobOperatorBase
from ..common.ai import (
    require_input_path,
    invoke_ai_setup_if_needed,
    production_device,
    require_environment,
    require_model,
)
from ..common.image import cleanup_image_input
from ..common.image_target import ImageEditTarget, image_edit_owner, owner_image

_HIDDEN = {"HIDDEN", "SKIP_SAVE"}

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


class UpscaleImage(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.upscale_image"
    bl_label = "Upscale"
    bl_description = "Upscale the image by 2x with an AI model"
    bl_options = {"UNDO"}
    job_type = "upscale-image"
    starting_message = "Starting image upscale"

    model: bpy.props.StringProperty(
        default="REALESRGAN_GENERAL_WDN_X4V3",
        options=_HIDDEN,
    )
    max_input_size: bpy.props.IntProperty(
        name="Max AI Input Size",
        description="Maximum input long edge used for AI upscale analysis",
        default=DEFAULT_MAX_AI_INPUT_SIZE,
        min=MIN_MAX_AI_INPUT_SIZE,
        max=MAX_MAX_AI_INPUT_SIZE,
        step=256,
        subtype="PIXEL",
        options=_HIDDEN,
    )
    input_path: bpy.props.StringProperty(options=_HIDDEN)
    delete_input: bpy.props.BoolProperty(default=False, options=_HIDDEN)

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        owner = image_edit_owner(context)
        return (
            owner is not None
            and upscale_input_size_allowed(
                owner_image(owner),
                configured_max_ai_input_size(context),
            )
            and not runtime.server_busy()
        )

    def invoke(self, context, _event):
        setup_result = invoke_ai_setup_if_needed(self)
        if setup_result is not None:
            return setup_result
        return self.execute(context)

    def execute(self, context):
        self.model = configured_upscale_model(context)
        self.max_input_size = configured_max_ai_input_size(context)
        try:
            self._image_target = ImageEditTarget.capture(context)
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        source_image = self._image_target.image
        if not upscale_input_size_allowed(source_image, self.max_input_size):
            self.report(
                {"ERROR"},
                "Image long edge must be smaller than Maximum AI Input Size "
                f"({self.max_input_size} px)",
            )
            return {"CANCELLED"}
        try:
            source_path, delete_input = self._image_target.prepare(context)
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        self.input_path = str(source_path)
        self.delete_input = delete_input
        result = super().execute(context)
        if "CANCELLED" in result:
            self.cleanup()
        return result

    def request(self, context):
        require_environment()
        require_model(self.model)
        return {
            "input": str(require_input_path(self.input_path)),
            "model": self.model,
            "device": production_device().lower(),
            "max_input_size": int(self.max_input_size),
        }

    def response(self, _context, result):
        self._image_target.apply(result.file("upscale"))
        model_label = upscale_model_label(self.model)
        return f"Image is upscaled with {model_label}"

    def cleanup(self):
        cleanup_image_input(self.input_path, self.delete_input)
        self._image_target = None
