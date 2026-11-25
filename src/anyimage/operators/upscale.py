from pathlib import Path
import tempfile

import bpy

from ..ai_preferences import configured_max_ai_input_size, configured_upscale_model
from ..server.model_catalog import UPSCALE_MODELS
from ..runtime import JobOperator
from ..common.ai import invoke_ai_setup_if_needed, model_job_parameters
from ..common.color_image import save_float_png
from ..common.hdr_image import is_hdr_source
from ..common.image import load_image_edit_result
from ..common.image_input import cleanup_image_input, prepare_ai_input
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


def load_upscale_result(source_image, output_path):
    """Load the upscaled PNG with the current source image settings."""
    output_path = Path(output_path)
    if not output_path.is_file():
        raise RuntimeError(f"Color result image does not exist: {output_path}")
    if source_image.is_float:
        import numpy as np
        from PIL import Image

        with tempfile.TemporaryDirectory(prefix="anyimage-upscale-") as directory:
            path = Path(directory) / "result.png"
            with Image.open(output_path) as png:
                rgba = np.asarray(png.convert("RGBA"), dtype=np.float32) / 255
                if source_image.alpha_mode == "PREMUL" and not source_image.colorspace_settings.is_data:
                    rgba[..., :3] *= rgba[..., 3:4]
                save_float_png(rgba, path)
            image = load_image_edit_result(path, source_image)
            try:
                image.pack()
                return image
            except Exception:
                bpy.data.images.remove(image)
                raise
    return load_image_edit_result(output_path, source_image)


def apply_upscale_result(target, path):
    target.validate_binding()
    result = load_upscale_result(target.image, path)
    return target.commit(result, prepare_undo=True)


class UpscaleImage(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.upscale_image"
    bl_label = "Upscale"
    bl_description = "Upscale the image by 2x with an AI model"
    bl_options = set()
    job_type = "upscale_image"
    starting_message = "Starting image upscale"

    _input_path = None

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        image = editable_still_image(context)
        return (
            image is not None
            and not is_hdr_source(image)
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
        if is_hdr_source(source_image, rgba):
            raise ValueError("Upscale requires a non-HDR image")
        if source_image.is_float and source_image.is_dirty:
            alpha = rgba[..., 3]
            space = source_image.colorspace_settings
            bounded_rgb = space.is_data or space.name in {"sRGB", "Linear Rec.709"}
            if alpha.min() < 0 or alpha.max() > 1 or (bounded_rgb and rgba[..., :3].min() < -1e-6):
                raise ValueError("Upscale requires a non-HDR image")
        if not upscale_input_size_allowed(source_image, max_input_size):
            raise ValueError(bpy.app.translations.pgettext_rpt(
                "Image long edge must be smaller than Maximum AI Input Size ({size} px)"
            ).format(size=max_input_size))
        self._input_path = prepare_ai_input(source_image, rgba)
        return {
            **parameters,
            "input": str(self._input_path),
            "max_input_size": max_input_size,
        }

    def response(self, _context, result):
        apply_upscale_result(self._image_target, result.file("upscale"))
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Upscale"):
            raise RuntimeError("Unable to create the Upscale Undo step")
        model_label = UPSCALE_MODELS[self._model].label
        return bpy.app.translations.pgettext_iface("Image is upscaled with {model}").format(model=model_label)

    def cleanup(self):
        cleanup_image_input(self._input_path)
        self._image_target = None
