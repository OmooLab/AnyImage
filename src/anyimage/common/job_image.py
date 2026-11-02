"""Prepare and commit image files for server jobs."""

from pathlib import Path
import bpy

from .color_image import load_material_color_image, save_color_png
from .image import COLOR_NORMALIZED_PROPERTY, image_rgba
from .image_input import prepare_image_input
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
        preview = build_recognition_rgba(
            rgba, associated=image.alpha_mode not in {"CHANNEL_PACKED", "NONE"}
        )
        output = path.parent / "analysis.png"
        save_color_png(preview, output, "sRGB")
        return output
    finally:
        bpy.data.images.remove(image)
