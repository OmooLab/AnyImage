"""Encode and pack HDR images."""

import bpy
import numpy as np

from .image import image_rgba


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
