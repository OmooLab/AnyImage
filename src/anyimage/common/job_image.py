"""Prepare and commit image files for server jobs."""

from pathlib import Path
import tempfile
import bpy

from .color_image import save_color_png
from .image import COLOR_NORMALIZED_PROPERTY
from .image_input import cleanup_image_input, prepare_image_input
from .hdr_image import build_recognition_rgba


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


def prepare_recognition_input(image, rgba):
    """Write a cropped sRGB PNG for inference, retaining source opacity."""
    color_space = image.colorspace_settings.name
    if image.is_float:
        rgba = build_recognition_rgba(rgba, image.alpha_mode, preserve_alpha=True)
        color_space = "sRGB"
    path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / "input.png"
    try:
        save_color_png(rgba, path, color_space, as_srgb=True)
    except Exception:
        cleanup_image_input(path)
        raise
    return path
