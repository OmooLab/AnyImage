"""Validate perspective quads and resample the selected image region."""

import math

from ...common.selection import (
    clip_polygon_halfplanes,
    trim_pixels_to_alpha,
)
from ...common.image import (
    projective_output_size,
    warp_projective_pixels,
)


MIN_INTERACTIVE_ASPECT = 0.05
MAX_INTERACTIVE_ASPECT = 20.0


def validate_perspective_quad(points, min_area=1e-6):
    """Return four convex corners without changing their correspondence."""
    import numpy as np

    quad = np.asarray(points, dtype=np.float64)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Rectify requires four valid image corners")
    edges = np.roll(quad, -1, axis=0) - quad
    if np.any(np.linalg.norm(edges, axis=1) < 2.0):
        raise ValueError("Rectify corners are too close together")
    crosses = np.cross(edges, np.roll(edges, -1, axis=0))
    if np.any(np.abs(crosses) <= 1e-8) or not (
        np.all(crosses > 0.0) or np.all(crosses < 0.0)
    ):
        raise ValueError("Rectify corners must define one convex quadrilateral")
    area = 0.5 * abs(
        float(
            np.dot(quad[:, 0], np.roll(quad[:, 1], -1))
            - np.dot(quad[:, 1], np.roll(quad[:, 0], -1))
        )
    )
    if area < min_area:
        raise ValueError("Draw a larger Rectify quad")
    return quad


def canonical_perspective_quad(points, min_area=1e-6):
    """Order four unordered points as source-oriented top-left through bottom-left."""
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Rectify requires four valid image corners")
    distances = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    distances += np.eye(4) * 1e9
    if float(distances.min()) < 2.0:
        raise ValueError("Rectify corners are too close together")
    center = points.mean(axis=0)
    ring = points[np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))]
    ring = validate_perspective_quad(ring, min_area)
    candidates = []
    for winding in (ring, ring[::-1]):
        for start in range(4):
            candidate = np.roll(winding, -start, axis=0)
            top = candidate[1] - candidate[0]
            left = candidate[3] - candidate[0]
            score = top[0] / np.linalg.norm(top) + left[1] / np.linalg.norm(left)
            candidates.append((float(score), -candidate[0, 1], -candidate[0, 0], candidate))
    return max(candidates, key=lambda item: item[:3])[3]


def perspective_quad_overlaps_image(points, image_size):
    import numpy as np

    width, height = image_size
    if min(width, height) <= 0:
        raise ValueError("The source image has no readable dimensions")
    clipped = np.asarray(clip_polygon_halfplanes(
        points, ((1, 0, 0), (-1, 0, width), (0, 1, 0), (0, -1, height))
    ))
    if clipped.ndim != 2 or len(clipped) < 3:
        return False
    area = 0.5 * abs(
        float(
            np.dot(clipped[:, 0], np.roll(clipped[:, 1], -1))
            - np.dot(clipped[:, 1], np.roll(clipped[:, 0], -1))
        )
    )
    return area > 1e-6


def perspective_quad_aspect(quad):
    """Estimate an initial output aspect from the visible quad edge lengths."""
    import numpy as np

    quad = validate_perspective_quad(quad)
    width = 0.5 * (
        np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])
    )
    height = 0.5 * (
        np.linalg.norm(quad[2] - quad[1]) + np.linalg.norm(quad[3] - quad[0])
    )
    return min(
        max(float(width / max(height, 1e-8)), MIN_INTERACTIVE_ASPECT),
        MAX_INTERACTIVE_ASPECT,
    )


def perspective_placement_bounds(quad, output_size, trim_bounds):
    """Map a rectified Alpha trim back to an approximate source-image rectangle."""
    quad = validate_perspective_quad(quad)
    source_left = math.floor(float(quad[:, 0].min()))
    source_top = math.floor(float(quad[:, 1].min()))
    source_right = math.ceil(float(quad[:, 0].max()))
    source_bottom = math.ceil(float(quad[:, 1].max()))
    output_width, output_height = (float(value) for value in output_size)
    trim_left, trim_top, trim_right, trim_bottom = trim_bounds
    source_width = source_right - source_left
    source_height = source_bottom - source_top
    return (
        source_left + trim_left * source_width / output_width,
        source_top + trim_top * source_height / output_height,
        source_left + trim_right * source_width / output_width,
        source_top + trim_bottom * source_height / output_height,
    )


def extract_perspective_pixels(
    source_pixels,
    source_size,
    quad,
    aspect_ratio,
):
    output_size = projective_output_size(quad, aspect_ratio)
    pixels = warp_projective_pixels(
        source_pixels, source_size, quad, output_size
    )
    pixels, trim_bounds = trim_pixels_to_alpha(pixels, (0, 0, *output_size))
    trimmed_size = (
        trim_bounds[2] - trim_bounds[0],
        trim_bounds[3] - trim_bounds[1],
    )
    placement_bounds = perspective_placement_bounds(
        quad, output_size, trim_bounds
    )
    return pixels, trimmed_size, placement_bounds
