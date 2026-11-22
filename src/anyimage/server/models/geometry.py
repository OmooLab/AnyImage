"""Geometry inference and its shared depth, validity and camera fields."""

from dataclasses import dataclass


@dataclass
class GeometryFrame:
    depth: object
    validity: object
    intrinsics: object
    normal: object | None = None
    points: object | None = None

    def __post_init__(self):
        import numpy as np

        depth = np.asarray(self.depth)
        validity = np.asarray(self.validity)
        intrinsics = np.asarray(self.intrinsics)
        if depth.dtype != np.float32 or depth.ndim != 2:
            raise ValueError("Geometry depth must be a 2D float32 field")
        if validity.dtype != np.float32 or validity.shape != depth.shape:
            raise ValueError("Geometry validity must match the depth as float32")
        if intrinsics.dtype != np.float32 or intrinsics.shape != (3, 3):
            raise ValueError("Geometry intrinsics must be a 3x3 float32 matrix")
        for name in ("normal", "points"):
            value = getattr(self, name)
            if value is None:
                continue
            field = np.asarray(value)
            if field.dtype != np.float32 or field.shape != (*depth.shape, 3):
                raise ValueError(
                    f"Geometry {name} must match the depth as three-channel float32"
                )


def _pixel_intrinsics(intrinsics, image_size):
    import numpy as np

    width, height = image_size
    result = np.asarray(intrinsics, dtype=np.float32).copy()
    result[0] *= width
    result[1] *= height
    result[2] = (0.0, 0.0, 1.0)
    return result


def infer_geometry(adapter, session, rgb, resolution_level, **options):
    """Infer full geometry with camera intrinsics expressed in pixels."""
    import numpy as np

    prediction = adapter.infer(session, rgb, resolution_level, **options)
    depth = np.asarray(prediction["depth"], dtype=np.float32)
    height, width = depth.shape
    return GeometryFrame(
        depth=depth,
        normal=np.asarray(prediction["normal"], dtype=np.float32),
        validity=np.asarray(prediction["mask"], dtype=np.float32),
        intrinsics=_pixel_intrinsics(prediction["intrinsics"], (width, height)),
        points=np.asarray(prediction["points"], dtype=np.float32),
    )
