"""Encode HDR images and prepare recognition previews."""

import bpy
import numpy as np

from .image import image_rgba


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


def save_hdr_result(rgba, path):
    """Save associated scene-linear RGBA as ZIP-compressed 32-bit EXR."""
    height, width = rgba.shape[:2]
    image = bpy.data.images.new("AnyImage HDR Result", width=width, height=height,
                                alpha=True, float_buffer=True)
    scene = None
    try:
        image.alpha_mode = "PREMUL"
        image.colorspace_settings.name = "Linear Rec.709"
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        scene = bpy.data.scenes.new("AnyImage HDR Export")
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


def create_packed_hdr(rgba, name, path, *, alpha_mode="PREMUL"):
    """Create a self-contained float image and verify its encoded pixels."""
    result = None
    save_hdr_result(rgba, path)
    try:
        result = bpy.data.images.load(str(path), check_existing=False)
        result.alpha_mode = alpha_mode
        if (not result.is_float
                or result.colorspace_settings.name != "Linear Rec.709"
                or not np.allclose(image_rgba(result), rgba, rtol=2e-6, atol=1e-7)):
            raise RuntimeError("The HDR result did not preserve float colors")
        result.pack()
        result.name = name
        return result
    except Exception:
        if result is not None:
            bpy.data.images.remove(result)
        raise
