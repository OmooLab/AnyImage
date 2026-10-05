"""Conversions between linear Rec.709 RGB, sRGB and OKLab."""

import numpy as np

_RGB_TO_LMS = np.asarray(
    (
        (0.4122214708, 0.2119034982, 0.0883024619),
        (0.5363325363, 0.6806995451, 0.2817188376),
        (0.0514459929, 0.1073969566, 0.6299787005),
    ),
    dtype=np.float32,
)
_LMS_TO_OKLAB = np.asarray(
    (
        (0.2104542553, 1.9779984951, 0.0259040371),
        (0.7936177850, -2.4285922050, 0.7827717662),
        (-0.0040720468, 0.4505937099, -0.8086757660),
    ),
    dtype=np.float32,
)
_OKLAB_TO_LMS = np.linalg.inv(_LMS_TO_OKLAB)
_LMS_TO_RGB = np.linalg.inv(_RGB_TO_LMS)

def linear_rgb_to_oklab(rgb):
    """Convert linear Rec.709 RGB values to OKLab."""
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.cbrt(rgb @ _RGB_TO_LMS) @ _LMS_TO_OKLAB


def oklab_to_linear_rgb(lab):
    """Convert OKLab to linear Rec.709 RGB without clipping."""
    lab = np.asarray(lab, dtype=np.float32)
    lms = lab @ _OKLAB_TO_LMS
    return (lms * lms * lms) @ _LMS_TO_RGB


def linear_rgb_to_srgb(rgb):
    """Encode linear RGB without clipping floating-point image values."""
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.where(
        rgb <= 0.0031308, rgb * 12.92,
        1.055 * np.maximum(rgb, 0.0) ** (1 / 2.4) - 0.055,
    )


def srgb_to_linear_rgb(rgb):
    """Decode sRGB without clipping floating-point image values."""
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.where(
        rgb <= 0.04045, rgb / 12.92,
        np.maximum((rgb + 0.055) / 1.055, 0.0) ** 2.4,
    )


def image_rgba_to_linear(image, rgba):
    """Decode byte business RGB as sRGB; float business RGB is linear Rec.709."""
    result = np.asarray(rgba, dtype=np.float32).copy()
    if not image.is_float:
        result[..., :3] = srgb_to_linear_rgb(result[..., :3])
    return result


def linear_rgba_to_image(image, rgba):
    """Encode linear colors for the destination Blender pixel buffer."""
    result = np.asarray(rgba, dtype=np.float32).copy()
    if not image.is_float:
        result[..., :3] = linear_rgb_to_srgb(result[..., :3])
    return result
