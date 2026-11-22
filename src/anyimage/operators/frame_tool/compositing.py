"""Composite linear image samples with independent RGB and Alpha coverage."""

import math
from concurrent.futures import ThreadPoolExecutor

from ...common.projective_image import PROJECTIVE_CHUNK_ROWS, sample_rgba
from .projection import frame_source_coordinates


def _composite_frame_samples(sources, screen_points):
    """Resolve independently sorted samples with an unweighted bottom RGB base."""
    import numpy as np

    samples, depths, coordinates = [], [], []
    for source in sources:
        normalized, depth, valid = frame_source_coordinates(source, screen_points)
        points = normalized * source["image_size"]
        points[~valid] = -1.0
        if len(sources) == 1:
            return sample_rgba(source["rgba"], points), valid
        sample = sample_rgba(source["pixels"], points)
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


def _frame_boundary_lines(source, pixel_step):
    import numpy as np

    width, height = source["region_size"]
    mapping = source["screen_to_source"] @ np.diag((1 / width, 1 / height, 1))
    u, v, w = mapping
    lines = [(line, True) for line in (u, v, w - u, w - v, w)]
    if source["perspective"]:
        lines.append((source["source_to_view"][2] @ mapping, False))
    return [(line, 0.5 * (abs(line[0] * pixel_step[0]) + abs(line[1] * pixel_step[1])), clips_image)
            for line, clips_image in lines]


def _frame_boundary_pixels(sources, boundary_lines, points, pixel_step):
    """Conservatively detect projected contour and depth-order crossings."""
    import numpy as np

    boundary = np.zeros(points.shape[:-1], dtype=bool)
    for lines in boundary_lines:
        positive = np.ones_like(boundary)
        negative = np.ones_like(boundary)
        source_boundary = np.zeros_like(boundary)
        for line, radius, clips_image in lines:
            value = points[..., 0] * line[0] + points[..., 1] * line[1] + line[2]
            if clips_image:
                positive &= value + radius >= 0
                negative &= value - radius <= 0
            source_boundary |= np.abs(value) < radius - 1e-10 * max(radius, 1e-20)
        boundary |= source_boundary & (positive | negative)
    if len(sources) > 1:
        first_order = None
        for offset in ((-0.499999, -0.499999), (0.499999, -0.499999),
                       (-0.499999, 0.499999), (0.499999, 0.499999)):
            screen = points + offset * pixel_step
            depths = []
            for source in sources:
                _, depth, valid = frame_source_coordinates(source, screen)
                depths.append(np.where(valid, depth, -math.inf))
            order = np.argsort(-np.stack(depths), axis=0, kind="stable")
            if first_order is None:
                first_order = order
            else:
                boundary |= np.any(order != first_order, axis=0)
    return boundary


def composite_frame_pixels(sources, frame_quad, output_size):
    """Composite linear Image Empty samples into Blender-order linear RGBA."""
    import numpy as np

    output_width, output_height = (int(value) for value in output_size)
    if min(output_width, output_height) <= 0:
        raise ValueError("The Frame output dimensions must be positive")
    sources = tuple(
        sorted(sources, key=lambda source: (source["active"], source["name"]))
    )
    if not sources or not sources[-1]["active"]:
        raise ValueError("Frame requires one active Image Empty")
    left, top = frame_quad[0]
    right, bottom = frame_quad[2]
    pixel_step = np.array(((right - left) / output_width, (bottom - top) / output_height))
    boundary_lines = [_frame_boundary_lines(source, pixel_step) for source in sources]
    output = np.zeros((output_height, output_width, 4), dtype=np.float32)
    target_x = left + (np.arange(output_width) + 0.5) * pixel_step[0]

    def composite_rows(row_start):
        row_end = min(row_start + PROJECTIVE_CHUNK_ROWS, output_height)
        target_y = top + (np.arange(row_start, row_end) + 0.5) * pixel_step[1]
        x, y = np.meshgrid(target_x, target_y)
        points = np.stack((x, y), axis=-1)
        composite, _ = _composite_frame_samples(sources, points)
        boundary = _frame_boundary_pixels(sources, boundary_lines, points, pixel_step)
        if np.any(boundary):
            edge_points = points[boundary]
            accumulated = np.zeros((len(edge_points), 4), dtype=np.float32)
            counts = np.zeros(len(edge_points), dtype=np.int32)
            for dy in (-0.375, -0.125, 0.125, 0.375):
                for dx in (-0.375, -0.125, 0.125, 0.375):
                    sample, hit = _composite_frame_samples(
                        sources,
                        edge_points + (dx, dy) * pixel_step,
                    )
                    accumulated += sample
                    counts += hit
            accumulated[..., 3] /= 16
            accumulated[..., :3] /= np.maximum(counts, 1)[..., None]
            composite[boundary] = accumulated
        output[row_start:row_end] = composite

    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(composite_rows, range(0, output_height, PROJECTIVE_CHUNK_ROWS)))
    output[..., 3][output[..., 3] <= 1e-8] = 0.0
    return np.flipud(output).ravel()
