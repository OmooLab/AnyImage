"""Prepare and commit image files for server jobs."""

from pathlib import Path
import shutil
import tempfile
import bpy
import numpy as np

from .color_image import load_material_color_image, save_color_png
from .image import (
    COLOR_NORMALIZED_PROPERTY, is_animated_image, image_is_packed, save_image_input,
    image_path, cleanup_image_input, image_rgba,
)


def prepare_image_input(image):
    """Prepare one still image for a Server job."""
    if is_animated_image(image):
        raise RuntimeError("Only still images are supported")
    if image_is_packed(image) or image.is_dirty or image.source == "GENERATED":
        return save_image_input(image)
    source_path = image_path(image)
    if not source_path.is_file():
        raise RuntimeError(f"Source image file does not exist: {source_path}")
    snapshot = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / source_path.name
    try:
        shutil.copyfile(source_path, snapshot)
    except OSError:
        cleanup_image_input(snapshot)
        raise
    return snapshot


def load_image_edit_result(source_image, output_path):
    """Load and pack the image file returned by a Job."""
    output_path = Path(output_path)
    if not output_path.is_file():
        raise RuntimeError(f"Color result image does not exist: {output_path}")
    result_image = None
    try:
        result_image = bpy.data.images.load(str(output_path), check_existing=False)
        result_image.colorspace_settings.name = source_image.colorspace_settings.name
        result_image.alpha_mode = source_image.alpha_mode
        if source_image.get(COLOR_NORMALIZED_PROPERTY):
            result_image[COLOR_NORMALIZED_PROPERTY] = True
        result_image.pack()
        result_image.name = source_image.name
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        if result_image is not None:
            bpy.data.images.remove(result_image, do_unlink=True)
        raise RuntimeError("Unable to load the color result") from error
    return result_image


def prepare_target_input(target):
    target.validate_binding()
    return prepare_image_input(target.image)


def apply_image_result(target, path):
    target.validate_binding()
    return target.commit(load_image_edit_result(target.image, path))


def material_analysis_input(color_path):
    """Return the byte color file or an HDR recognition preview in the same directory."""

    path = Path(color_path)
    if path.suffix == ".png":
        return path
    image = load_material_color_image(path)
    try:
        rgba = image_rgba(image)
        if image.alpha_mode == "NONE":
            rgba[..., 3] = 1
        preview = recognition_rgba(
            rgba, associated=image.alpha_mode not in {"CHANNEL_PACKED", "NONE"}
        )
        output = path.parent / "analysis.png"
        save_color_png(preview, output, "sRGB")
        return output
    finally:
        bpy.data.images.remove(image)


def recognition_rgba(rgba, *, associated=True):
    """Tone-map scene-linear pixels for sRGB recognition without changing the source."""
    alpha = rgba[..., 3:4]
    rgb = rgba[..., :3].astype(np.float64)
    if associated:
        rgb = np.divide(rgb, alpha, out=np.zeros_like(rgb), where=alpha > 0)
    rgb = np.maximum(rgb, 0)
    luminance = rgb @ np.array([0.2126, 0.7152, 0.0722])
    rgb /= 1 + luminance[..., None]
    encoded = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * rgb ** (1 / 2.4) - 0.055)
    preview = np.ones(rgba.shape, dtype=np.float32)
    preview[..., :3] = np.clip(encoded, 0, 1) * alpha
    return preview
