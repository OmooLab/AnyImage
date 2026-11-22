"""Load geometry images and read their depth pixels."""

import bpy

from .image import image_base_name


DEPTH_ALPHA_THRESHOLD = 0.95


def depth_data_name(source_object):
    return f"{image_base_name(source_object.data)}_depth.exr"


def normal_data_name(source_object):
    return f"{image_base_name(source_object.data)}_normal.png"


def load_normal_result_image(path, source_object):
    """Load, name, configure, and pack a generated normal image."""
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.name = normal_data_name(source_object)
        image.colorspace_settings.is_data = True
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise


def load_depth_result_image(path, source_object):
    """Load and configure a generated Depth texture."""
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.name = depth_data_name(source_object)
        image.colorspace_settings.is_data = True
        image.alpha_mode = "CHANNEL_PACKED"
        return image
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise


def camera_depth_values(pixels):
    """Return top-down camera Z and validity from a loaded Depth texture."""
    import numpy as np

    depth = pixels[..., 2]
    valid = (pixels[..., 3] > DEPTH_ALPHA_THRESHOLD) & np.isfinite(depth) & (depth > 0.0)
    return depth, valid
