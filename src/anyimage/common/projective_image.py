"""Projective image transforms and alpha-aware pixel sampling."""

import math


MAX_PROJECTIVE_OUTPUT_DIMENSION = 8192


MAX_PROJECTIVE_OUTPUT_PIXELS = 16_777_216


PROJECTIVE_CHUNK_ROWS = 256


def homography_from_points(source, target):
    """Return a projective transform mapping four source points to target."""
    import numpy as np

    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if source.shape != (4, 2) or target.shape != (4, 2):
        raise ValueError("A homography requires four source and target points")
    rows = []
    values = []
    for (x, y), (u, v) in zip(source, target):
        rows.extend(
            (
                (x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y),
                (0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y),
            )
        )
        values.extend((u, v))
    matrix = np.asarray(rows, dtype=np.float64)
    if np.linalg.cond(matrix) > 1e12:
        raise ValueError("The projective transform is too degenerate")
    coefficients = np.linalg.solve(matrix, np.asarray(values, dtype=np.float64))
    return np.append(coefficients, 1.0).reshape((3, 3))


def transform_homography(points, matrix):
    """Transform 2D points by one homography."""
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    if points.ndim < 2 or points.shape[-1] != 2:
        raise ValueError("Projective points must contain X and Y")
    flat = points.reshape((-1, 2))
    homogeneous = np.column_stack((flat, np.ones(len(flat), dtype=np.float64)))
    mapped = homogeneous @ np.asarray(matrix, dtype=np.float64).T
    denominator = mapped[:, 2]
    if np.any(np.abs(denominator) <= 1e-12):
        raise ValueError("The projective transform reaches infinity")
    mapped = mapped[:, :2] / denominator[:, None]
    if not np.isfinite(mapped).all():
        raise ValueError("The projective transform is not finite")
    return mapped.reshape(points.shape)


def projective_output_size(
    quad,
    aspect_ratio,
    max_dimension=MAX_PROJECTIVE_OUTPUT_DIMENSION,
    max_pixels=MAX_PROJECTIVE_OUTPUT_PIXELS,
):
    """Choose a detail-preserving output size for a source-space quad."""
    import numpy as np

    quad = np.asarray(quad, dtype=np.float64)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Projective output requires four valid corners")
    if not math.isfinite(aspect_ratio) or aspect_ratio <= 0.0:
        raise ValueError("Projective output aspect ratio must be greater than zero")
    width_pixels = 0.5 * (
        np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])
    )
    height_pixels = 0.5 * (
        np.linalg.norm(quad[2] - quad[1]) + np.linalg.norm(quad[3] - quad[0])
    )
    if min(width_pixels, height_pixels) <= 1e-8:
        raise ValueError("Projective output corners are too close together")
    height = (aspect_ratio * width_pixels + height_pixels) / (
        aspect_ratio * aspect_ratio + 1.0
    )
    width = aspect_ratio * height
    dimension_scale = float(max_dimension) / max(width, height)
    pixel_scale = math.sqrt(float(max_pixels) / max(width * height, 1.0))
    scale = min(1.0, dimension_scale, pixel_scale)
    return max(2, int(round(width * scale))), max(2, int(round(height * scale)))


def premultiplied_rgba(source_pixels, source_size):
    """Return top-down premultiplied RGBA pixels."""
    import numpy as np

    width, height = (int(value) for value in source_size)
    if min(width, height) <= 0:
        raise ValueError("Image dimensions must be positive")
    source = np.asarray(source_pixels, dtype=np.float32)
    if source.size != width * height * 4:
        raise ValueError("The image pixels do not match its dimensions")
    source = np.flipud(source.reshape((height, width, 4))).copy()
    source[:, :, :3] *= source[:, :, 3:4]
    return source


def sample_rgba(source, source_points):
    """Bilinearly sample top-down RGBA at image-boundary coordinates."""
    import numpy as np

    source = np.asarray(source, dtype=np.float32)
    points = np.asarray(source_points, dtype=np.float64)
    if source.ndim != 3 or source.shape[2] != 4:
        raise ValueError("The source must contain RGBA pixels")
    if points.shape[-1] != 2:
        raise ValueError("Sample points must contain X and Y")
    height, width = source.shape[:2]
    flat = points.reshape((-1, 2))
    mapped_x = flat[:, 0]
    mapped_y = flat[:, 1]
    valid = (
        np.isfinite(mapped_x)
        & np.isfinite(mapped_y)
        & (mapped_x >= 0.0)
        & (mapped_x <= width)
        & (mapped_y >= 0.0)
        & (mapped_y <= height)
    )
    pixel_x = np.clip(mapped_x - 0.5, 0.0, width - 1.0)
    pixel_y = np.clip(mapped_y - 0.5, 0.0, height - 1.0)
    x0 = np.floor(pixel_x).astype(np.int64)
    y0 = np.floor(pixel_y).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = (pixel_x - x0)[:, None]
    fy = (pixel_y - y0)[:, None]
    sampled = (
        source[y0, x0] * (1.0 - fx) * (1.0 - fy)
        + source[y0, x1] * fx * (1.0 - fy)
        + source[y1, x0] * (1.0 - fx) * fy
        + source[y1, x1] * fx * fy
    )
    sampled[~valid] = 0.0
    return sampled.reshape((*points.shape[:-1], 4))


def straight_rgba(premultiplied):
    """Convert premultiplied RGBA and bleed edge RGB into transparent pixels."""
    import numpy as np

    rgba = np.asarray(premultiplied, dtype=np.float32).copy()
    alpha = rgba[..., 3]
    visible = alpha > 1e-8
    rgb = rgba[..., :3]
    rgb[visible] /= alpha[visible, None]
    rgba[~visible] = 0.0
    if rgba.ndim == 3:
        unfilled = ~visible

        def fill_edge(target, source):
            candidates = unfilled[target] & visible[source]
            target_rgb = rgb[target]
            target_rgb[candidates] = rgb[source][candidates]
            unfilled[target][candidates] = False

        fill_edge((slice(1, None), slice(None)), (slice(None, -1), slice(None)))
        fill_edge((slice(None, -1), slice(None)), (slice(1, None), slice(None)))
        fill_edge((slice(None), slice(1, None)), (slice(None), slice(None, -1)))
        fill_edge((slice(None), slice(None, -1)), (slice(None), slice(1, None)))
        fill_edge((slice(1, None), slice(1, None)), (slice(None, -1), slice(None, -1)))
        fill_edge((slice(1, None), slice(None, -1)), (slice(None, -1), slice(1, None)))
        fill_edge((slice(None, -1), slice(1, None)), (slice(1, None), slice(None, -1)))
        fill_edge((slice(None, -1), slice(None, -1)), (slice(1, None), slice(1, None)))
    return rgba


def warp_projective_pixels(source_pixels, source_size, quad, output_size):
    """Warp one source quad into Blender-order straight RGBA pixels."""
    import numpy as np

    output_width, output_height = (int(value) for value in output_size)
    if min(output_width, output_height) <= 0:
        raise ValueError("Projective output dimensions must be positive")
    source = premultiplied_rgba(source_pixels, source_size)
    target = np.asarray(
        (
            (0.0, 0.0),
            (float(output_width), 0.0),
            (float(output_width), float(output_height)),
            (0.0, float(output_height)),
        ),
        dtype=np.float64,
    )
    output_to_source = homography_from_points(target, quad)
    output = np.zeros((output_height, output_width, 4), dtype=np.float32)
    target_x = np.arange(output_width, dtype=np.float64) + 0.5
    for row_start in range(0, output_height, PROJECTIVE_CHUNK_ROWS):
        row_end = min(row_start + PROJECTIVE_CHUNK_ROWS, output_height)
        target_y = np.arange(row_start, row_end, dtype=np.float64) + 0.5
        x, y = np.meshgrid(target_x, target_y)
        points = np.stack((x, y), axis=-1)
        mapped = transform_homography(points, output_to_source)
        output[row_start:row_end] = sample_rgba(source, mapped)
    return np.flipud(straight_rgba(output)).ravel()
