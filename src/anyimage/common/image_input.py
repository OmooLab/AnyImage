"""Prepare independent image input files and release their temporary directories."""

from pathlib import Path
import shutil
import tempfile

import bpy

from .image import is_animated_image


def prepare_image_input(image):
    """Prepare one still image for a Server job."""
    if is_animated_image(image):
        raise RuntimeError("Only still images are supported")
    if image.packed_files or image.is_dirty or image.source == "GENERATED":
        return save_image_input(image)
    source_path = Path(bpy.path.abspath(image.filepath_from_user())).expanduser()
    if not source_path.is_file():
        raise RuntimeError(f"Source image file does not exist: {source_path}")
    snapshot = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / source_path.name
    try:
        shutil.copyfile(source_path, snapshot)
    except OSError:
        cleanup_image_input(snapshot)
        raise
    return snapshot


def save_image_input(image):
    """Export the current Blender pixels as an independent PNG input."""
    output_path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / "input.png"
    original_file_format = image.file_format
    try:
        image.file_format = "PNG"
        image.save(filepath=str(output_path), save_copy=True)
    except (OSError, RuntimeError, ValueError) as error:
        cleanup_image_input(output_path)
        raise RuntimeError("Unable to export the image") from error
    finally:
        image.file_format = original_file_format
    if not output_path.is_file():
        cleanup_image_input(output_path)
        raise RuntimeError("Blender did not export the image")
    return output_path


def cleanup_image_input(path):
    """Remove a prepared input and its temporary container."""
    if not path:
        return
    path = Path(path)
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
    except OSError:
        pass
