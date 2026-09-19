"""Prepare isolated material color files from static image bounds."""

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import bpy

from .image import cleanup_image_input, image_base_name, image_is_packed, image_rgba, is_animated_image


def require_static_color_image(image):
    """Reject animated inputs before preparing material resources."""
    if is_animated_image(image):
        raise ValueError("Material conversion supports static images only")


def _save_byte_color(rgba, path, color_space):
    import numpy as np

    height, width = rgba.shape[:2]
    image = bpy.data.images.new("Material Color Export", width=width, height=height, alpha=True)
    try:
        image.colorspace_settings.name = color_space
        image.alpha_mode = "STRAIGHT"
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        image.file_format = "PNG"
        image.save(filepath=str(path), save_copy=True)
        if not path.is_file():
            raise RuntimeError("Unable to export the material color image")
    finally:
        bpy.data.images.remove(image)


def prepare_material_color_input(source, bounds=None, rgba=None):
    """Export source bounds with interpretation matching the encoded color file."""
    import numpy as np
    from .hdr_image import save_hdr_result

    require_static_color_image(source)
    width, height = map(int, source.size)
    if (source.is_float and source.source == "FILE" and not source.is_dirty
            and not image_is_packed(source) and source.alpha_mode == "STRAIGHT"):
        # Read the encoded float colors without applying a second alpha multiplication.
        reader = source.copy()
        try:
            reader.alpha_mode = "PREMUL"
            rgba = image_rgba(reader)
        finally:
            bpy.data.images.remove(reader)
    else:
        rgba = image_rgba(source) if rgba is None else np.asarray(rgba, dtype=np.float32)
    if rgba.shape != (height, width, 4):
        raise ValueError("The source RGBA does not match the Blender Image")
    left, top, right, bottom = (0, 0, width, height) if bounds is None else map(int, bounds)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("The material color bounds are outside the image")
    cropped = rgba[top:bottom, left:right]
    suffix = ".exr" if source.is_float else ".png"
    path = Path(tempfile.mkdtemp(prefix="anyimage-color-")) / ("color" + suffix)
    try:
        if source.is_float:
            # Store float colors directly; the EXR interpretation is applied on load.
            save_hdr_result(cropped, path)
        else:
            _save_byte_color(cropped, path, source.colorspace_settings.name)
        path.with_suffix(".json").write_text(json.dumps({
            "name": image_base_name(source) + "_color" + suffix,
            "color_space": "Linear Rec.709" if source.is_float else source.colorspace_settings.name,
            "alpha_mode": "PREMUL" if source.is_float and source.alpha_mode == "STRAIGHT" else source.alpha_mode,
        }), encoding="utf-8")
        return path
    except Exception:
        cleanup_material_color_input(path)
        raise


def material_analysis_input(color_path):
    """Return the byte color file or an HDR recognition preview in the same directory."""
    from .hdr_image import recognition_rgba

    path = Path(color_path)
    if path.suffix == ".png":
        return path
    image = load_material_color_image(path)
    try:
        rgba = image_rgba(image)
        if image.alpha_mode == "NONE":
            rgba[..., 3] = 1
        preview = recognition_rgba(rgba, associated=image.alpha_mode not in {"CHANNEL_PACKED", "NONE"})
        output = path.parent / "analysis.png"
        _save_byte_color(preview, output, "sRGB")
        return output
    finally:
        bpy.data.images.remove(image)


def cleanup_material_color_input(path):
    """Release the directory owned by a prepared material color input."""
    if path:
        cleanup_image_input(Path(path).parent, True)


def load_material_color_image(path):
    """Load an independent packed Color image using its file interpretation."""
    path = Path(path)
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.name = metadata["name"]
        image.colorspace_settings.name = metadata["color_space"]
        image.alpha_mode = metadata["alpha_mode"]
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image)
        raise


@contextmanager
def material_color_image(source=None, *, bounds=None, rgba=None, input_path=None):
    """Own a prepared color image through material creation and clean failed results."""
    owned = input_path is None
    path = prepare_material_color_input(source, bounds, rgba) if owned else Path(input_path)
    image = None
    try:
        image = load_material_color_image(path)
        yield image
    except Exception:
        if image is not None:
            bpy.data.images.remove(image, do_unlink=True)
            image = None
        raise
    finally:
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)
        if owned:
            cleanup_material_color_input(path)
