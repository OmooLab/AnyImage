"""Encode HDR images and build their recognition previews."""

from concurrent.futures import ThreadPoolExecutor

import bpy
import numpy as np

from .image import image_rgba
from .color_space import linear_rgb_to_srgb


def save_hdr_image(rgba, path):
    """Save associated scene-linear RGBA as ZIP-compressed 32-bit EXR."""
    height, width = rgba.shape[:2]
    image = bpy.data.images.new("Any Image HDR Result", width=width, height=height,
                                alpha=True, float_buffer=True)
    scene = None
    try:
        image.alpha_mode = "PREMUL"
        image.colorspace_settings.name = "Linear Rec.709"
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        scene = bpy.data.scenes.new("Any Image HDR Export")
        settings = scene.render.image_settings
        settings.file_format = "OPEN_EXR"
        settings.color_mode = "RGBA"
        settings.color_depth = "32"
        settings.exr_codec = "ZIP"
        image.save_render(str(path), scene=scene)
    finally:
        if scene is not None:
            bpy.data.scenes.remove(scene)
        bpy.data.images.remove(image)


def create_hdr_image(rgba, name, path, *, alpha_mode="PREMUL"):
    """Create a float image and verify its encoded pixels."""
    result = None
    save_hdr_image(rgba, path)
    try:
        result = bpy.data.images.load(str(path), check_existing=False)
        result.alpha_mode = alpha_mode
        if (not result.is_float
                or result.colorspace_settings.name != "Linear Rec.709"
                or not np.allclose(image_rgba(result), rgba, rtol=2e-6, atol=1e-7)):
            raise RuntimeError("The HDR result did not preserve float colors")
        result.name = name
        return result
    except Exception:
        if result is not None:
            bpy.data.images.remove(result)
        raise


def build_recognition_rgba(image, rgba):
    """Encode Blender's linear float pixels for recognition, preserving sRGB source brightness."""
    alpha_mode = image.alpha_mode
    tone_map = image.colorspace_settings.name != "sRGB"
    preview = np.empty(rgba.shape, dtype=np.float32)

    def map_rows(top):
        rows = slice(top, top + 64)
        source = rgba[rows]
        if not np.isfinite(source).all():
            raise ValueError("HDR recognition requires finite RGBA values")
        alpha = source[..., 3]
        rgb = np.array(source[..., :3].transpose(2, 0, 1), dtype=np.float64, order="C")
        np.maximum(rgb, 0, out=rgb)
        divisor = 1.0 if alpha_mode in {"CHANNEL_PACKED", "NONE"} else np.where(alpha > 0, alpha, np.inf)
        if tone_map:
            # Unpremultiplying then tone mapping gives RGB / (alpha + luminance).
            luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            divisor = divisor + luminance
        rgb /= divisor
        encoded = linear_rgb_to_srgb(rgb.astype(np.float32))
        preview[rows, :, :3] = np.clip(encoded, 0, 1).transpose(1, 2, 0)
        preview[rows, :, 3] = 1 if alpha_mode == "NONE" else np.clip(alpha, 0, 1)

    # Workers only touch independent NumPy rows; all Blender access stays on the caller.
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(map_rows, range(0, len(rgba), 64)))
    return preview
