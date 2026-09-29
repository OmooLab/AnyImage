"""Copy complete source images into regular surface tiles."""

import numpy as np

from ...common.image import image_pixels


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
