"""Write model-space depth textures."""

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
    if not np.any((validity > 0.5) & np.isfinite(frame.depth) & (frame.depth > 0)):
        raise ValueError("Geometry frame contains no valid depth pixels")
    rgba = np.empty((*validity.shape, 4), dtype=np.float32)
    rgba[..., :3] = points
    rgba[..., 3] = alpha * validity
    return write_float_exr(rgba, output_path)
