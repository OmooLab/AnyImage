"""Calibrate depth scales, clipping distances, and fitted plane directions."""

PLANE_VARIANCE_FLOOR_RATIO = 0.025
REFERENCE_DEPTH_PERCENTILE = 95.0
REFERENCE_DEPTH_RANGE_FACTOR = 1.1
REFERENCE_DEPTH_BASELINE = 8.0
DEPTH_LIMIT_MEDIAN_FACTOR = 1.5
FLAT_DEPTH_DIRECTION = (0.0, 1.0, 0.0)


def depth_node_direction(direction):
    """Map a canonical XZ depth-plane direction to the node socket axes."""
    x, y, z = direction
    return (-x, -z, y)


def reference_and_median_depth(values):
    """Return the near-field 95th percentile and median of the selected depths."""
    import numpy as np

    if not values.size:
        return REFERENCE_DEPTH_BASELINE, REFERENCE_DEPTH_BASELINE
    median = float(np.median(values))
    near = values[values <= REFERENCE_DEPTH_RANGE_FACTOR * median]
    return float(np.percentile(near, REFERENCE_DEPTH_PERCENTILE)), median


def depth_limit_preset(model_median, model_reference, uniform_scale):
    """Return the far clipping distance behind the reference plane."""
    return max((DEPTH_LIMIT_MEDIAN_FACTOR * model_median - model_reference) * uniform_scale, 0.0)


def depth_plane_limit_preset(values, model_median, model_reference, uniform_scale):
    """Keep the far scene while trimming the most distant depth outliers."""
    import numpy as np

    limit = depth_limit_preset(model_median, model_reference, uniform_scale)
    if not values.size:
        return limit
    far_depth = np.percentile(values, 99.5)
    return max(limit, (far_depth - model_reference) * uniform_scale)


def _weighted_depth_plane(coordinates, values, weights):
    import numpy as np

    total = float(np.sum(weights))
    if total <= 1e-12:
        return np.zeros(3, dtype=np.float32)
    center = np.sum(coordinates * weights[:, None], axis=0) / total
    value_center = float(np.sum(values * weights) / total)
    centered = coordinates - center
    covariance = (centered * weights[:, None]).T @ centered / total
    cross = centered.T @ (weights * (values - value_center)) / total
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    largest = max(float(eigenvalues[-1]), 0.0)
    if largest <= 1e-12:
        slopes = np.zeros(2, dtype=np.float64)
    else:
        supported = np.maximum(eigenvalues, largest * PLANE_VARIANCE_FLOOR_RATIO)
        slopes = eigenvectors @ ((eigenvectors.T @ cross) / supported)
    intercept = value_center - float(center @ slopes)
    return np.asarray((*slopes, intercept), dtype=np.float32)


def fit_depth_direction(coordinates, depth, valid, uniform_scale):
    """Fit a robust metric depth plane on the XZ plane and return its direction.

    The direction is canonical `(slope_x, 1, slope_z)`. A selection without
    usable samples returns `FLAT_DEPTH_DIRECTION`.
    """
    import numpy as np

    coordinates = np.asarray(coordinates, dtype=np.float64)
    depth = np.asarray(depth, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    if coordinates.ndim != 2 or coordinates.shape[1] != 2:
        raise ValueError("Depth plane coordinates must have two components")
    if depth.shape != (len(coordinates),) or valid.shape != depth.shape:
        raise ValueError("Depth plane samples and validity must match coordinates")
    if not uniform_scale > 0.0:
        raise ValueError("Depth Uniform Scale must be positive")
    usable = valid & np.isfinite(depth) & (depth > 0.0)
    values = depth[usable] * float(uniform_scale)
    points = coordinates[usable]
    if len(points) < 2:
        return FLAT_DEPTH_DIRECTION
    plane = _weighted_depth_plane(points, values, np.ones(len(values), dtype=np.float64))
    for _ in range(3):
        residual = values - points @ plane[:2] - plane[2]
        centered = residual - np.median(residual)
        abs_residual = np.abs(centered)
        scale = max(float(np.median(abs_residual)) * 1.4826, 1e-6)
        weights = np.minimum(1.0, (2.5 * scale) / np.maximum(abs_residual, 1e-12))
        plane = _weighted_depth_plane(points, values, weights)
    direction = np.asarray((plane[0], 1.0, plane[1]), dtype=np.float64)
    direction /= np.linalg.norm(direction)
    return tuple(float(value) for value in direction)


def _sample_valid_bilinear(values, valid, x, y):
    import numpy as np

    height, width = values.shape
    x = np.clip(x, 0.0, max(width - 1, 0))
    y = np.clip(y, 0.0, max(height - 1, 0))
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = x - x0
    fy = y - y0
    samples = np.stack(
        (
            values[y0, x0],
            values[y0, x1],
            values[y1, x0],
            values[y1, x1],
        ),
        axis=1,
    )
    weights = np.stack(
        (
            (1.0 - fx) * (1.0 - fy),
            fx * (1.0 - fy),
            (1.0 - fx) * fy,
            fx * fy,
        ),
        axis=1,
    )
    sample_valid = np.stack(
        (
            valid[y0, x0],
            valid[y0, x1],
            valid[y1, x0],
            valid[y1, x1],
        ),
        axis=1,
    )
    samples[~sample_valid] = 0.0
    weights *= sample_valid
    totals = weights.sum(axis=1)
    result = np.zeros(len(x), dtype=np.float32)
    usable = totals > 1e-8
    result[usable] = (samples[usable] * weights[usable]).sum(axis=1) / totals[usable]
    return result, usable


def fit_symmetry_depth_direction(depth, valid, vertices, vertex_uv, uniform_scale):
    """Fit the Depth Symmetry base plane direction from base shape UV samples."""
    import numpy as np

    vertices = np.asarray(vertices, dtype=np.float32)
    uv = np.asarray(vertex_uv, dtype=np.float32)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("Depth Symmetry vertices must have three components")
    if uv.shape != (len(vertices), 2):
        raise ValueError("Depth Symmetry UV coordinates do not match its vertices")
    height, width = depth.shape
    sampled, sampled_usable = _sample_valid_bilinear(
        depth,
        valid,
        uv[:, 0] * max(width - 1, 0),
        (1.0 - uv[:, 1]) * max(height - 1, 0),
    )
    return fit_depth_direction(
        vertices[:, (0, 2)],
        sampled,
        sampled_usable,
        uniform_scale,
    )


def fit_image_depth_direction(depth, valid, bounds, uniform_scale):
    """Fit the depth direction across a complete XZ image plane."""
    import numpy as np

    height, width = depth.shape
    x_min, x_max, y_min, y_max = bounds
    x = x_min + (np.arange(width) + 0.5) / width * (x_max - x_min)
    z = y_min + (np.arange(height) + 0.5) / height * (y_max - y_min)
    xx, zz = np.meshgrid(x, z)
    coordinates = np.column_stack((xx.ravel(), zz.ravel()))
    return fit_depth_direction(
        coordinates,
        depth.ravel(),
        valid.ravel(),
        uniform_scale,
    )


def depth_uniform_scale(bounds, metadata, model_reference):
    """Convert model camera units uniformly into Image Empty local distance."""
    import numpy as np

    intrinsics = metadata["intrinsics"]
    width, height = metadata["image_size"]
    x_min, x_max, y_min, y_max = bounds
    plane_width = x_max - x_min
    plane_height = y_max - y_min
    fx, fy = float(intrinsics[0][0]), float(intrinsics[1][1])
    scale_x = plane_width * fx / (max(width - 1, 1) * model_reference)
    scale_y = plane_height * fy / (max(height - 1, 1) * model_reference)
    return float(np.sqrt(scale_x * scale_y))
