"""Rectify preview images, overlays, and interactive aspect controls."""

import math

import bpy

from ...common.image import image_base_name
from ...common.image_preview import draw_centered_text
from .geometry import (
    MAX_INTERACTIVE_ASPECT,
    MIN_INTERACTIVE_ASPECT,
)


PREVIEW_TEXTURE_SIZE = 512
ASPECT_PIXELS_PER_DOUBLE = 240.0
ASPECT_PRESETS = (
    ("9 : 16", 9.0 / 16.0),
    ("3 : 4", 3.0 / 4.0),
    ("1 : 1", 1.0),
    ("4 : 3", 4.0 / 3.0),
    ("16 : 9", 16.0 / 9.0),
)


def preview_polygon(points):
    """Return a non-crossing preview hull for the current unordered clicks."""
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    if len(points) < 3:
        return points
    center = points.mean(axis=0)
    return points[np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))]


def interactive_preview_polygon(points, cursor):
    """Return the clicked points plus one distinct moving cursor point."""
    vertices = list(points)
    if (
        cursor is not None
        and vertices
        and len(vertices) < 4
        and math.dist(vertices[-1], cursor) >= 2.0
    ):
        vertices.append(cursor)
    return preview_polygon(vertices)


def aspect_ratio_from_mouse(initial_ratio, horizontal_delta):
    ratio = initial_ratio * math.pow(
        2.0, float(horizontal_delta) / ASPECT_PIXELS_PER_DOUBLE
    )
    return min(max(ratio, MIN_INTERACTIVE_ASPECT), MAX_INTERACTIVE_ASPECT)


def snapped_aspect_ratio(aspect_ratio):
    label, ratio = min(
        ASPECT_PRESETS,
        key=lambda preset: abs(math.log(aspect_ratio / preset[1])),
    )
    return ratio, label


def aspect_ratio_label(aspect_ratio, preset_label=None):
    if preset_label is not None:
        return preset_label
    if aspect_ratio >= 1.0:
        return f"{aspect_ratio:.2f} : 1"
    return f"1 : {1.0 / aspect_ratio:.2f}"


def draw_aspect_hud(bounds, aspect_ratio, preset_label=None):
    left, bottom, width, height = bounds
    center_x = left + width * 0.5
    draw_centered_text(
        aspect_ratio_label(aspect_ratio, preset_label),
        center_x,
        bottom + height * 0.5 - 10.0,
        22,
        (0.25, 0.65, 1.0, 1.0),
    )
    draw_centered_text(
        "Move horizontally  •  Ctrl snap  •  LMB confirm  •  Backspace edit",
        center_x,
        bottom - 26.0,
        13,
        (0.85, 0.9, 1.0, 1.0),
    )


def create_perspective_preview_image(source_image, pixels):
    image = bpy.data.images.new(
        f"{image_base_name(source_image)}.rectify-preview",
        width=PREVIEW_TEXTURE_SIZE,
        height=PREVIEW_TEXTURE_SIZE,
        alpha=True,
    )
    try:
        image.colorspace_settings.name = "sRGB"
        image.alpha_mode = "STRAIGHT"
        image.pixels.foreach_set(pixels)
        image.update()
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise
    return image
