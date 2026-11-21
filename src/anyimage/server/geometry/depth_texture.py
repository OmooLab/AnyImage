"""Write model-space depth textures and their compact metadata."""

import json
from pathlib import Path

from ..media.exr import write_float_exr


def write_depth_texture(frame, output_path, *, alpha):
    """Write camera-space XYZ and alpha-weighted model validity as float RGBA."""
    import numpy as np

    if frame.points is None:
        raise ValueError("Depth requires a point field")
    points = np.asarray(frame.points, dtype=np.float32)
    validity = np.asarray(frame.validity, dtype=np.float32)
    alpha = np.asarray(alpha, dtype=np.float32)
    if alpha.shape != validity.shape:
        raise ValueError("Depth Alpha must match the validity dimensions")
    if not np.isfinite(points).all():
        raise ValueError("Point field contains non-finite values")
    rgba = np.empty((*validity.shape, 4), dtype=np.float32)
    rgba[..., :3] = points
    rgba[..., 3] = alpha * validity
    return write_float_exr(rgba, output_path)


def write_depth_metadata(frame, output_path):
    """Write camera values needed to scale a model-space depth texture."""
    import numpy as np

    depth = np.asarray(frame.depth, dtype=np.float32)
    validity = np.asarray(frame.validity, dtype=np.float32)
    intrinsics = np.asarray(frame.intrinsics, dtype=np.float32)
    if depth.ndim != 2 or validity.shape != depth.shape:
        raise ValueError("Depth metadata dimensions do not match")
    if intrinsics.shape != (3, 3):
        raise ValueError("Depth metadata requires 3x3 camera intrinsics")
    valid = (validity > 0.5) & np.isfinite(depth) & (depth > 0.0)
    if not valid.any():
        raise ValueError("Geometry frame contains no valid depth pixels")
    metadata = {
        "image_size": [int(depth.shape[1]), int(depth.shape[0])],
        "intrinsics": intrinsics.tolist(),
    }
    output_path = Path(output_path)
    output_path.write_text(
        json.dumps(metadata, separators=(",", ":")),
        encoding="utf-8",
    )
    return output_path
