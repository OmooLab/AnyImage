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


def source_encoded_rgba(image, rgba):
    """Read float source samples, retaining unsaved or externally replaced pixels."""
    space = image.colorspace_settings.name
    mode = image.alpha_mode
    if image.source == "FILE" and not image.is_dirty:
        # Reading raw avoids lossy OCIO round trips and preserves hidden colors.
        reader = image.copy()
        try:
            if tuple(reader.size) == tuple(image.size) and np.array_equal(image_rgba(reader), rgba, equal_nan=True):
                reader.colorspace_settings.name = "Non-Color"
                reader.alpha_mode = "CHANNEL_PACKED"
                encoded = image_rgba(reader)
                if mode == "PREMUL" and not image.colorspace_settings.is_data:
                    alpha = encoded[..., 3:4]
                    encoded[..., :3] /= np.where(alpha > 0, alpha, 1)
                return encoded
        finally:
            bpy.data.images.remove(reader)
    encoded = rgba.copy()
    if image.colorspace_settings.is_data:
        return encoded
    if mode in {"PREMUL", "STRAIGHT"}:
        alpha = rgba[..., 3:4]
        encoded[..., :3] /= np.where(alpha > 0, alpha, 1)
    if space == "sRGB":
        from .color_space import linear_rgb_to_srgb
        encoded[..., :3] = linear_rgb_to_srgb(encoded[..., :3])
    elif space != "Linear Rec.709":
        import tempfile
        from pathlib import Path

        height, width = rgba.shape[:2]
        reader = bpy.data.images.new("Source encoding", width, height, alpha=True, float_buffer=True)
        try:
            encoded[..., 3] = 1
            reader.pixels.foreach_set(encoded[::-1].ravel())
            with tempfile.TemporaryDirectory(prefix="anyimage-color-") as directory:
                path = Path(directory) / "source.exr"
                save_image_exr(reader, path, space)
                raw = bpy.data.images.load(str(path), check_existing=False)
                try:
                    raw.colorspace_settings.name = "Non-Color"
                    encoded = image_rgba(raw)
                finally:
                    bpy.data.images.remove(raw)
            encoded[..., 3] = rgba[..., 3]
        finally:
            bpy.data.images.remove(reader)
    return encoded


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
