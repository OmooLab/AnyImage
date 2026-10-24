"""Prepare and commit image files for server jobs."""

from pathlib import Path
import bpy
from .image import is_animated_image, image_is_packed, save_packed_image, image_path


def prepare_image_input(image, scene):
    """Prepare one still image for a Server job."""
    if is_animated_image(image):
        raise RuntimeError("Only still images are supported")
    if image_is_packed(image):
        return save_packed_image(image, scene), True
    source_path = image_path(image)
    if not source_path.is_file():
        raise RuntimeError(f"Source image file does not exist: {source_path}")
    return source_path, False


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
        result_image.pack()
        result_image.name = source_image.name
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        if result_image is not None:
            bpy.data.images.remove(result_image, do_unlink=True)
        raise RuntimeError("Unable to load the color result") from error
    return result_image


def prepare_target_input(target, context):
    target.validate()
    return prepare_image_input(target.image, context.scene)


def apply_image_result(target, path):
    target.validate()
    return target.commit(load_image_edit_result(target.image, path))
