"""Prepare and commit HDR background-removal inputs."""

from dataclasses import dataclass
from pathlib import Path
import tempfile

import bpy
import numpy as np

from ..common.image import cleanup_image_input, image_content_state, image_rgba, is_animated_image, restore_image_content
from ..common.image_target import has_other_image_user
from ..common.hdr_image import recognition_rgba, create_packed_hdr


@dataclass
class HdrBackgroundInput:
    """Own the submitted pixels and color interpretation of an HDR still."""

    rgba: np.ndarray
    color_space: str
    alpha_mode: str
    source: str
    path: Path

    @classmethod
    def prepare(cls, image):
        if is_animated_image(image):
            raise RuntimeError("HDR background removal supports still images only")
        if image.source not in {"FILE", "GENERATED"}:
            raise RuntimeError("HDR background removal requires a file or generated image")
        if image.colorspace_settings.is_data:
            raise RuntimeError("HDR background removal requires a color image with opacity alpha")
        rgba = image_rgba(image).copy()
        if not np.isfinite(rgba).all() or np.any((rgba[..., 3] < 0) | (rgba[..., 3] > 1)):
            raise RuntimeError("HDR image contains invalid color or alpha values")
        path = Path(tempfile.mkdtemp(prefix="anyimage-hdr-")) / "input.png"
        preview = None
        try:
            height, width = rgba.shape[:2]
            preview = bpy.data.images.new("AnyImage HDR Preview", width=width, height=height,
                                          alpha=True)
            preview.colorspace_settings.name = "sRGB"
            preview.alpha_mode = "STRAIGHT"
            preview_source = rgba.copy()
            if image.alpha_mode == "NONE":
                preview_source[..., 3] = 1
            preview_rgba = recognition_rgba(
                preview_source, associated=image.alpha_mode not in {"CHANNEL_PACKED", "NONE"},
            )
            preview.pixels.foreach_set(np.flipud(preview_rgba).ravel())
            preview.file_format = "PNG"
            preview.save(filepath=str(path), save_copy=True)
            if not path.is_file():
                raise RuntimeError("Blender did not export the HDR recognition preview")
        except Exception:
            cleanup_image_input(path, True)
            raise
        finally:
            if preview is not None:
                bpy.data.images.remove(preview)
        return cls(rgba, image.colorspace_settings.name, image.alpha_mode, image.source, path)

    def apply(self, target, alpha_path, *, prepare_undo=False):
        target.validate()
        image = target.image
        if (not image.is_float or image.colorspace_settings.name != self.color_space
                or image.alpha_mode != self.alpha_mode or image.source != self.source
                or not np.array_equal(image_rgba(image), self.rgba)):
            raise RuntimeError("The source HDR image changed; run Remove Background again")
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
        with tempfile.TemporaryDirectory(prefix="anyimage-hdr-result-") as directory:
            result = create_packed_hdr(
                rgba, image.name, Path(directory) / "result.exr", alpha_mode="CHANNEL_PACKED",
            )
            original_state = None
            try:
                if (prepare_undo and (image.is_dirty or image.source == "GENERATED")
                        and not has_other_image_user(target.owner)):
                    original_state = image_content_state(image)
                    baseline_rgba = self.rgba.copy()
                    if self.alpha_mode == "NONE":
                        baseline_rgba[..., 3] = 1
                    baseline = create_packed_hdr(
                        baseline_rgba, image.name, Path(directory) / "source.exr",
                        alpha_mode="CHANNEL_PACKED" if self.alpha_mode == "CHANNEL_PACKED" else "PREMUL",
                    )
                    try:
                        restore_image_content(image, image_content_state(baseline))
                    finally:
                        bpy.data.images.remove(baseline)
                    if "FINISHED" not in bpy.ops.ed.undo_push(message="Before HDR Background Removal"):
                        raise RuntimeError("Unable to preserve the source HDR image for Undo")
            except Exception:
                bpy.data.images.remove(result)
                if original_state is not None:
                    restore_image_content(image, original_state)
                raise
            try:
                return target.commit(result, isolate_shared=True)
            except Exception:
                if original_state is not None:
                    restore_image_content(image, original_state)
                raise
