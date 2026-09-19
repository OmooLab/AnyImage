import bpy
import numpy as np
import pytest


@pytest.fixture
def hdr_texture(texture):
    image = bpy.data.images.new("HDR source", width=4, height=3, alpha=True, float_buffer=True)
    image.alpha_mode = "PREMUL"
    rgba = np.tile([4.0, 2.0, -0.25, 0.5], (3, 4, 1)).astype(np.float32)
    rgba[0, 0] = [9, 3, -0.5, 0]
    rgba[2, 3] = [25, 12, 6, 1]
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    texture.image = image
    return texture
