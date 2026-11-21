"""Write floating-point RGBA images in OpenEXR scanline format."""

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
        raise ValueError("EXR image must contain RGBA float pixels")
    height, width = rgba.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("EXR image dimensions must be positive")
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
        offsets = first_block + np.arange(height, dtype=np.uint64) * block_size
        output.write(offsets.astype("<u8", copy=False))
        for row in range(height):
            output.write(struct.pack("<iI", row, row_size))
            # Each scanline stores complete A, B, G and R channels in order.
            output.write(np.ascontiguousarray(rgba[row, :, ::-1].T, dtype="<f4"))
    return output_path
