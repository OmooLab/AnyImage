"""Prepare recognition input and apply the predicted mask to the submitted colors."""

from dataclasses import dataclass
from pathlib import Path
import tempfile

import bpy
import numpy as np

from ..ai_preferences import configured_background_model
from ..common.ai import invoke_ai_setup_if_needed, model_job_parameters
from ..common.color_image import save_float_png
from ..common.hdr_image import is_hdr_source, save_hdr_image, source_encoded_rgba
from ..common.image import ImageFormat, create_image_edit_result, load_image_edit_result
from ..common.image_input import cleanup_image_input, prepare_ai_input
from ..common.image_target import ImageEditTarget, editable_still_image
from ..runtime import JobOperator


@dataclass
class BackgroundInput:
    """Keep the submitted pixels for applying the predicted opacity."""

    rgba: np.ndarray
    image_format: ImageFormat
    path: Path
    hdr: bool = False

    @classmethod
    def prepare(cls, image, rgba):
        source = rgba
        if image.is_float:
            if image.source not in {"FILE", "GENERATED"}:
                raise RuntimeError("HDR background removal requires a file or generated image")
            if image.colorspace_settings.is_data:
                raise RuntimeError("HDR background removal requires a color image with opacity alpha")
            source = source_encoded_rgba(image, rgba)
            if not np.isfinite(source).all() or np.any((source[..., 3] < 0) | (source[..., 3] > 1)):
                raise RuntimeError("HDR image contains invalid color or alpha values")
        path = prepare_ai_input(image, rgba, source_rgba=source)
        return cls(source, ImageFormat.capture(image), path, is_hdr_source(image, rgba))

    def apply(self, target, alpha_path, *, prepare_undo=False):
        target.validate_binding()
        image = target.image
        try:
            alpha = np.load(alpha_path, allow_pickle=False)
        except (OSError, ValueError, EOFError) as error:
            raise RuntimeError("Unable to read the background alpha result") from error
        if not isinstance(alpha, np.ndarray):
            alpha.close()
            raise RuntimeError("Invalid background alpha result")
        if (alpha.dtype != np.float32 or alpha.shape != self.rgba.shape[:2]
                or not np.isfinite(alpha).all() or np.any((alpha < 0) | (alpha > 1))):
            raise RuntimeError("Invalid background alpha result")
        fmt = self.image_format
        rgba = self.rgba.copy()
        rgba[..., 3] *= alpha
        if not fmt.is_float:
            result = create_image_edit_result(image, rgba[::-1].ravel(), rgba.shape[1::-1])
            return target.commit(result, prepare_undo=prepare_undo)
        if fmt.alpha_mode == "PREMUL":
            source_alpha = self.rgba[..., 3:4]
            rgba[..., :3] *= np.where(source_alpha > 0, source_alpha, 1) * alpha[..., None]
        with tempfile.TemporaryDirectory(prefix="anyimage-background-") as directory:
            if self.hdr:
                path = Path(directory) / "result.exr"
                save_hdr_image(rgba, path)
            else:
                path = Path(directory) / "result.png"
                save_float_png(rgba, path)
            result = load_image_edit_result(path, image)
            return target.commit(result, prepare_undo=prepare_undo)


class RemoveImageBackground(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.remove_image_background"
    bl_label = "Remove Background"
    bl_description = "Remove the image background with the selected AI model"
    bl_options = {"REGISTER"}
    job_type = "remove_background"
    starting_message = "Starting image background removal"

    _background_input = None

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return editable_still_image(context) is not None and runtime.can_submit()

    def invoke(self, context, _event):
        setup_result = invoke_ai_setup_if_needed(self)
        if setup_result is not None:
            return setup_result
        return self.execute(context)

    def request(self, context):
        parameters = model_job_parameters(configured_background_model(context))
        try:
            self._image_target, rgba = ImageEditTarget.capture(context)
            self._background_input = BackgroundInput.prepare(self._image_target.image, rgba)
        except MemoryError as error:
            raise RuntimeError("Not enough memory to prepare the image") from error
        return {**parameters, "input": str(self._background_input.path)}

    def response(self, _context, result):
        self._background_input.apply(self._image_target, result.file("alpha"), prepare_undo=True)
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Remove Background"):
            raise RuntimeError("Unable to create the Remove Background Undo step")
        return "Image background is removed"

    def cleanup(self):
        try:
            if self._background_input is not None:
                cleanup_image_input(self._background_input.path)
        finally:
            self._image_target = None
            self._background_input = None
