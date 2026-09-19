"""Rectify preview images, overlays, and interactive aspect controls."""

import math

import bpy

from ...common.image import image_base_name
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


def preview_draw_bounds(region_size, aspect_ratio):
    region_width, region_height = (float(value) for value in region_size)
    available_width = min(region_width * 0.65, 640.0)
    available_height = min(region_height * 0.65, 640.0)
    if aspect_ratio >= available_width / available_height:
        width = available_width
        height = width / aspect_ratio
    else:
        height = available_height
        width = height * aspect_ratio
    return (
        (region_width - width) * 0.5,
        (region_height - height) * 0.5,
        width,
        height,
    )


def draw_preview_frame(bounds):
    import gpu
    from gpu_extras.batch import batch_for_shader

    left, bottom, width, height = bounds
    vertices = (
        (left, bottom),
        (left + width, bottom),
        (left + width, bottom + height),
        (left, bottom + height),
        (left, bottom),
    )
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2.0)
    shader.bind()
    shader.uniform_float("color", (0.12, 0.52, 1.0, 1.0))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


def draw_centered_text(text, center_x, baseline_y, size, color):
    import blf

    font_id = 0
    blf.size(font_id, size)
    width, _height = blf.dimensions(font_id, text)
    x = center_x - width * 0.5
    blf.position(font_id, x + 1.0, baseline_y - 1.0, 0.0)
    blf.color(font_id, 0.0, 0.0, 0.0, 0.9)
    blf.draw(font_id, text)
    blf.position(font_id, x, baseline_y, 0.0)
    blf.color(font_id, *color)
    blf.draw(font_id, text)


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


def preview_texture_draw_options(blender_version):
    if tuple(blender_version) >= (5, 0, 0):
        return {"is_scene_linear_with_rec709_srgb_target": True}
    return {}
