"""Rectify preview images, overlays, and interactive aspect controls."""

import math

from .geometry import (
    MAX_INTERACTIVE_ASPECT,
    MIN_INTERACTIVE_ASPECT,
    corners_in_cyclic_order,
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
    return corners_in_cyclic_order(vertices)


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
