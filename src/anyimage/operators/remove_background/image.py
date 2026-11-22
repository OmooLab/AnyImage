"""Prepare recognition input and apply the predicted mask to the submitted colors."""

from dataclasses import dataclass
from pathlib import Path
import tempfile

import bpy
import numpy as np

from ...common.image import (
    create_image_edit_result,
    has_other_image_user,
    image_content_signature,
    pack_image_result,
    image_content_state,
    image_rgba,
    restore_image_content,
)
from ...common.job_image import prepare_recognition_input
from ...common.hdr_image import create_hdr_image


@dataclass
class BackgroundInput:
    """Keep the submitted pixels for applying the predicted opacity."""

    rgba: np.ndarray
    alpha_mode: str
    path: Path

    @classmethod
    def prepare(cls, image, rgba):
        if image.is_float:
            if image.source not in {"FILE", "GENERATED"}:
                raise RuntimeError("HDR background removal requires a file or generated image")
            if image.colorspace_settings.is_data:
                raise RuntimeError("HDR background removal requires a color image with opacity alpha")
            if not np.isfinite(rgba).all() or np.any((rgba[..., 3] < 0) | (rgba[..., 3] > 1)):
                raise RuntimeError("HDR image contains invalid color or alpha values")
        path = prepare_recognition_input(image, rgba)
        return cls(rgba, image.alpha_mode, path)

    def apply(self, target, alpha_path, *, prepare_undo=False):
        target.validate()
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
        # Keep RGB independent of the new mask, including completely transparent pixels.
        rgba = self.rgba.copy()
        if self.alpha_mode == "NONE":
            rgba[..., 3] = 1
        rgba[..., 3] *= alpha
        if not image.is_float:
            result = create_image_edit_result(image, rgba[::-1].ravel(), rgba.shape[1::-1])
            if self.alpha_mode == "NONE":
                result.alpha_mode = "STRAIGHT"
            return target.commit(result)
        with tempfile.TemporaryDirectory(prefix="anyimage-hdr-result-") as directory:
            result = create_hdr_image(
                rgba, image.name, Path(directory) / "result.exr", alpha_mode="CHANNEL_PACKED",
            )
            original_state = None
            original_signature = target.content_signature
            try:
                if (prepare_undo and (image.is_dirty or image.source == "GENERATED")
                        and not has_other_image_user(target.owner)):
                    original_state = image_content_state(image)
                    baseline_rgba = image_rgba(image, original_state["pixels"])
                    baseline_alpha_mode = image.alpha_mode
                    if baseline_alpha_mode == "NONE":
                        baseline_rgba = baseline_rgba.copy()
                        baseline_rgba[..., 3] = 1
                    baseline = create_hdr_image(
                        baseline_rgba, image.name, Path(directory) / "source.exr",
                        alpha_mode="CHANNEL_PACKED" if baseline_alpha_mode == "CHANNEL_PACKED" else "PREMUL",
                    )
                    try:
                        pack_image_result(baseline, image)
                    finally:
                        bpy.data.images.remove(baseline)
                    target.content_signature = image_content_signature(image)
                    if "FINISHED" not in bpy.ops.ed.undo_push(message="Before HDR Background Removal"):
                        raise RuntimeError("Unable to preserve the source HDR image for Undo")
            except Exception:
                bpy.data.images.remove(result)
                if original_state is not None:
                    restore_image_content(image, original_state)
                    target.content_signature = original_signature
                raise
            try:
                return target.commit(result)
            except Exception:
                if original_state is not None:
                    restore_image_content(image, original_state)
                    target.content_signature = original_signature
                raise
