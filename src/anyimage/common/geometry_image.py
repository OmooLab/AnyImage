"""Load geometry images and read their depth metadata and pixel buffers."""

import json
from pathlib import Path

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


def load_depth_result_image(path, source_object, metadata):
    """Load, validate, name, configure, and pack a generated Depth texture."""
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = metadata["image_size"]
        if tuple(int(value) for value in image.size) != (width, height):
            raise ValueError("Depth texture dimensions do not match its metadata")
        image.name = depth_data_name(source_object)
        image.colorspace_settings.is_data = True
        image.alpha_mode = "CHANNEL_PACKED"
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise


def load_depth_metadata(path):
    """Read and validate the compact camera metadata beside a Depth texture."""
    metadata = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        image_size = tuple(int(value) for value in metadata["image_size"])
        intrinsics = tuple(
            tuple(float(value) for value in row)
            for row in metadata["intrinsics"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Depth metadata is invalid") from error
    if (
        len(image_size) != 2
        or min(image_size) <= 0
        or len(intrinsics) != 3
        or any(len(row) != 3 for row in intrinsics)
        or intrinsics[0][0] <= 0.0
        or intrinsics[1][1] <= 0.0
    ):
        raise ValueError("Depth metadata is invalid")
    return {
        "image_size": image_size,
        "intrinsics": intrinsics,
    }


def camera_depth_values(image):
    """Return top-down camera Z and validity from a loaded Depth texture."""
    import numpy as np

    width, height = (int(value) for value in image.size)
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = np.flipud(pixels.reshape((height, width, 4)))
    depth = pixels[..., 2]
    valid = (pixels[..., 3] > DEPTH_ALPHA_THRESHOLD) & np.isfinite(depth) & (depth > 0.0)
    return depth, valid
