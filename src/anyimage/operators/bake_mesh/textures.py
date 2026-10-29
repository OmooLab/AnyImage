"""Prepare tiled colors and scaled emission textures for static materials."""

import bpy
import numpy as np

from ...common.color_space import linear_rgb_to_srgb
from ...common.image import image_pixels


def create_emission_color_image(image):
    """Encode linear emission as an sRGB PNG and a constant strength."""
    pixels = image_pixels(image).reshape(-1, 4)
    if not np.isfinite(pixels).all():
        raise ValueError("Emission baking requires finite RGBA values")
    pixels[:, :3] = np.maximum(pixels[:, :3], 0)
    strength = max(1.0, float(pixels[:, :3].max()))
    pixels[:, :3] = linear_rgb_to_srgb(pixels[:, :3] / strength)
    pixels[:, 3] = 1
    result = bpy.data.images.new(image.name, width=image.size[0], height=image.size[1], alpha=True)
    try:
        result.colorspace_settings.name = "sRGB"
        result.alpha_mode = "PREMUL"
        result.file_format = "PNG"
        result.pixels.foreach_set(pixels.ravel())
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
    result = np.zeros((height * len(tiles), width * len(tiles[0]), 4), dtype=pixels.dtype)
    for y, row in enumerate(tiles):
        for x, region in enumerate(row):
            if region is not None:
                result[y * height:(y + 1) * height, x * width:(x + 1) * width] = (
                    pixels[:, ::-1] if region in (1, 2) else pixels)
    return result
