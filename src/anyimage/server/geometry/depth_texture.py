"""Write model-space depth textures and their compact metadata."""

import json
import struct
from pathlib import Path


def _exr_attribute(name, kind, value):
    return (
        name.encode("ascii")
        + b"\0"
        + kind.encode("ascii")
        + b"\0"
        + struct.pack("<I", len(value))
        + value
    )


def _exr_channels():
    return b"".join(
        name.encode("ascii")
        + b"\0"
        + struct.pack("<iB3xii", 2, 0, 1, 1)
        for name in ("A", "B", "G", "R")
    ) + b"\0"


def write_float_exr(rgba, output_path):
    """Write one uncompressed scanline RGBA OpenEXR without extra dependencies."""
    import numpy as np

    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("Depth texture must contain RGBA float pixels")
    height, width = rgba.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Depth texture dimensions must be positive")
    box = struct.pack("<iiii", 0, 0, width - 1, height - 1)
    header = b"".join(
        (
            struct.pack("<II", 20000630, 2),
            _exr_attribute("channels", "chlist", _exr_channels()),
            _exr_attribute("compression", "compression", b"\0"),
            _exr_attribute("dataWindow", "box2i", box),
            _exr_attribute("displayWindow", "box2i", box),
            _exr_attribute("lineOrder", "lineOrder", b"\0"),
            _exr_attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0)),
            _exr_attribute(
                "screenWindowCenter",
                "v2f",
                struct.pack("<ff", 0.0, 0.0),
            ),
            _exr_attribute("screenWindowWidth", "float", struct.pack("<f", 1.0)),
            b"\0",
        )
    )
    row_size = width * 4 * 4
    block_size = 8 + row_size
    first_block = len(header) + height * 8
    output_path = Path(output_path)
    with output_path.open("wb") as output:
        output.write(header)
        for row in range(height):
            output.write(struct.pack("<Q", first_block + row * block_size))
        for row in range(height):
            output.write(struct.pack("<iI", row, row_size))
            for channel in (3, 2, 1, 0):
                output.write(
                    np.asarray(rgba[row, :, channel], dtype="<f4").tobytes()
                )
    return output_path


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
