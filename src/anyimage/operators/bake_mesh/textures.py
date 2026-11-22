"""Prepare tiled colors and scaled emission textures for static materials."""

import bpy
import numpy as np

from ...common.color_space import linear_rgb_to_srgb
from ...common.color_image import linear_color_rgba
from ...common.image import image_pixels


def create_emission_color_image(image, rgba=None, *, alpha_mode=None):
    """Encode nonnegative linear emission as sRGB PNG and constant strength."""
    linear = linear_color_rgba(image, rgba, alpha_mode=alpha_mode)
    if not np.isfinite(linear).all():
        raise ValueError("Emission baking requires finite RGBA values")
    rgb = linear[..., :3]
    np.maximum(rgb, 0, out=rgb)
    strength = max(1.0, float(rgb.max()))
    rgb[:] = linear_rgb_to_srgb(rgb / strength)
    linear[..., 3] = 1
    height, width = linear.shape[:2]
    result = bpy.data.images.new(image.name, width=width, height=height, alpha=True)
    try:
        result.colorspace_settings.name = "sRGB"
        result.alpha_mode = "PREMUL"
        result.file_format = "PNG"
        result.pixels.foreach_set(linear[::-1].ravel())
        result.update()
        result.pack()
        return result, strength
    except Exception:
        bpy.data.images.remove(result)
        raise


def build_color_tiles(image, tiles):
    """Copy tiles with rear and mirrored horizontal flips composed together."""
    width, height = image.size
    pixels = image_pixels(image).reshape(height, width, 4)
    if tiles == ((0,),):
        return pixels
    result = np.zeros((height * len(tiles), width * len(tiles[0]), 4), dtype=pixels.dtype)
    for y, row in enumerate(tiles):
        for x, region in enumerate(row):
            if region is not None:
                result[y * height:(y + 1) * height, x * width:(x + 1) * width] = (
                    pixels[:, ::-1] if region in (1, 2) else pixels)
    return result


def merge_color_alpha(pixels, opacity, source):
    """Merge baked opacity into Color pixels, preserving associated float RGB."""
    pixels = pixels.reshape(-1, 4)
    opacity = np.clip(opacity, 0, 1)
    if source.is_float and source.alpha_mode in {"STRAIGHT", "PREMUL"}:
        factor = np.divide(opacity, pixels[:, 3], out=np.zeros_like(opacity), where=pixels[:, 3] > 0)
        pixels[:, :3] *= factor[:, None]
    pixels[:, 3] = opacity
