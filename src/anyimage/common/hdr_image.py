"""Identify HDR sources and encode scene-linear EXR images."""

import bpy
import numpy as np

from .image import image_rgba


def save_image_exr(image, path, color_space):
    """Write a 32-bit RGBA EXR in the requested color space."""
    scene = bpy.data.scenes.new("Any Image EXR Export")
    try:
        settings = scene.render.image_settings
        settings.file_format = "OPEN_EXR"
        settings.color_mode = "RGBA"
        settings.color_depth = "32"
        settings.exr_codec = "ZIP"
        settings.color_management = "OVERRIDE"
        settings.linear_colorspace_settings.name = color_space
        image.save_render(str(path), scene=scene)
    finally:
        bpy.data.scenes.remove(scene)


def save_hdr_image(rgba, path):
    """Save associated scene-linear RGBA as ZIP-compressed 32-bit EXR."""
    height, width = rgba.shape[:2]
    image = bpy.data.images.new("Any Image HDR Result", width=width, height=height,
                                alpha=True, float_buffer=True)
    try:
        image.alpha_mode = "PREMUL"
        image.colorspace_settings.name = "Linear Rec.709"
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        save_image_exr(image, path, "Linear Rec.709")
    finally:
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


def is_hdr_source(image, rgba=None):
    """Classify the source before cropping so each job maps the same highlights."""
    if not image.is_float:
        return False
    if image.file_format in {"OPEN_EXR", "OPEN_EXR_MULTILAYER", "HDR"}:
        return True
    if image.source == "GENERATED" and image.colorspace_settings.name != "sRGB":
        return True
    if rgba is None or (not image.is_dirty and image.file_format in {"PNG", "JPEG2000"}):
        return False
    # Blender's color conversion can put SDR white slightly above 1.
    alpha = rgba[..., 3:4]
    associated = not image.colorspace_settings.is_data and image.alpha_mode in {"STRAIGHT", "PREMUL"}
    ceiling = alpha if associated else 1.0
    rgb = rgba[..., :3]
    if not image.colorspace_settings.is_data and image.colorspace_settings.name not in {"sRGB", "Linear Rec.709"}:
        # Wide-gamut SDR can exceed a Rec.709 primary while staying below reference white.
        luminance = rgb @ np.array([.2126, .7152, .0722], np.float32)
        return bool(np.any(luminance[..., None] > ceiling + .0005))
    return bool(np.any(rgb > ceiling + .0005))
