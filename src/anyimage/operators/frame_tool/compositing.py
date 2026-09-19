"""Composite projected image samples with independent RGB and Alpha coverage."""

import math
from ...common.image import (
    PROJECTIVE_CHUNK_ROWS,
    homography_from_points,
    sample_rgba,
    transform_homography,
)
from .projection import frame_source_coordinates


def _pixel_quad(image_size):
    width, height = (float(value) for value in image_size)
    if min(width, height) <= 0.0:
        raise ValueError("The source image has no readable dimensions")
    return ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))


def _composite_frame_samples(sources, screen_points):
    """Resolve independently sorted samples with an unweighted bottom RGB base."""
    import numpy as np

    samples, depths, coordinates = [], [], []
    for source in sources:
        points, depth, valid, _ = frame_source_coordinates(source, screen_points)
        sample = sample_rgba(source["pixels"], points)
        sample[~valid] = 0
        depths.append(np.where(valid, depth, -math.inf))
        samples.append(sample)
        coordinates.append(points)
    samples = np.stack(samples)
    depths = np.stack(depths)
    order = np.argsort(-depths, axis=0, kind="stable")
    bottom = order[0]
    covered = np.isfinite(np.take_along_axis(depths, bottom[None], axis=0)[0])
    result = np.zeros_like(samples[0])
    for index, source in enumerate(sources):
        selected = covered & (bottom == index)
        if np.any(selected):
            result[..., :3][selected] = sample_rgba(
                source["rgba"], coordinates[index][selected]
            )[..., :3]
    for index in range(len(sources)):
        layer = np.take_along_axis(samples, order[index][None, ..., None], axis=0)[0]
        alpha = layer[..., 3:4]
        result[..., 3:4] = alpha + result[..., 3:4] * (1 - alpha)
        if index:
            result[..., :3] = layer[..., :3] + result[..., :3] * (1 - alpha)
    return result, covered


def _frame_boundary_pixels(sources, points, output_to_screen):
    """Conservatively detect projected contour and depth-order crossings."""
    import numpy as np

    boundary = np.zeros(points.shape[:-1], dtype=bool)
    for source in sources:
        width, height = source["region_size"]
        mapping = source["screen_to_source"] @ np.diag((1 / width, 1 / height, 1)) @ output_to_screen
        u, v, w = mapping
        lines = [u, v, u - w, v - w, w]
        positive = np.ones_like(boundary)
        negative = np.ones_like(boundary)
        for line in (u, v, w - u, w - v, w):
            radius = 0.5 * (abs(line[0]) + abs(line[1]))
            value = points[..., 0] * line[0] + points[..., 1] * line[1] + line[2]
            positive &= value + radius >= 0
            negative &= value - radius <= 0
        source_boundary = np.zeros_like(boundary)
        if source["perspective"]:
            lines.append(source["source_to_view"][2] @ mapping)
        for line in lines:
            radius = 0.5 * (abs(line[0]) + abs(line[1]))
            value = points[..., 0] * line[0] + points[..., 1] * line[1] + line[2]
            source_boundary |= np.abs(value) < radius - 1e-10 * max(radius, 1e-20)
        boundary |= source_boundary & (positive | negative)
    if len(sources) > 1:
        first_order = None
        for offset in ((-0.499999, -0.499999), (0.499999, -0.499999),
                       (-0.499999, 0.499999), (0.499999, 0.499999)):
            screen = transform_homography(points + offset, output_to_screen)
            depths = []
            for source in sources:
                _, depth, valid, _ = frame_source_coordinates(source, screen)
                depths.append(np.where(valid, depth, -math.inf))
            order = np.argsort(-np.stack(depths), axis=0, kind="stable")
            if first_order is None:
                first_order = order
            else:
                boundary |= np.any(order != first_order, axis=0)
    return boundary


def composite_frame_pixels(sources, frame_quad, output_size):
    """Composite projected Image Empty sources into one Blender-order RGBA image."""
    import numpy as np

    output_width, output_height = (int(value) for value in output_size)
    if min(output_width, output_height) <= 0:
        raise ValueError("The Frame output dimensions must be positive")
    sources = tuple(
        sorted(sources, key=lambda source: (source["active"], source["name"]))
    )
    if not sources or not sources[-1]["active"]:
        raise ValueError("Frame requires one active Image Empty")
    output_quad = _pixel_quad(output_size)
    output_to_screen = homography_from_points(output_quad, frame_quad)
    output = np.zeros((output_height, output_width, 4), dtype=np.float32)
    covered = np.zeros((output_height, output_width), dtype=bool)
    target_x = np.arange(output_width, dtype=np.float64) + 0.5
    for row_start in range(0, output_height, PROJECTIVE_CHUNK_ROWS):
        row_end = min(row_start + PROJECTIVE_CHUNK_ROWS, output_height)
        target_y = np.arange(row_start, row_end, dtype=np.float64) + 0.5
        x, y = np.meshgrid(target_x, target_y)
        points = np.stack((x, y), axis=-1)
        composite, coverage = _composite_frame_samples(
            sources, transform_homography(points, output_to_screen)
        )
        boundary = _frame_boundary_pixels(sources, points, output_to_screen)
        if np.any(boundary):
            edge_points = points[boundary]
            accumulated = np.zeros((len(edge_points), 4), dtype=np.float32)
            counts = np.zeros(len(edge_points), dtype=np.int32)
            for dy in (-0.375, -0.125, 0.125, 0.375):
                for dx in (-0.375, -0.125, 0.125, 0.375):
                    sample, hit = _composite_frame_samples(
                        sources,
                        transform_homography(edge_points + (dx, dy), output_to_screen),
                    )
                    accumulated += sample
                    counts += hit
            accumulated[..., 3] /= 16
            accumulated[..., :3] /= np.maximum(counts, 1)[..., None]
            composite[boundary] = accumulated
            coverage[boundary] = counts > 0
        covered[row_start:row_end] = coverage
        output[row_start:row_end] = composite
    output[..., 3][output[..., 3] <= 1e-8] = 0.0
    output[~covered] = 0.0
    return np.flipud(output).ravel()
