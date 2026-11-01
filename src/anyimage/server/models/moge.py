from .geometry import GeometryFrame
from . import model_adapter


def _pixel_intrinsics(intrinsics, image_size):
    import numpy as np

    width, height = image_size
    result = np.asarray(intrinsics, dtype=np.float32).copy()
    result[0] *= width
    result[1] *= height
    result[2] = (0.0, 0.0, 1.0)
    return result


def _geometry_frame(prediction, include_points):
    import numpy as np

    depth = np.asarray(prediction["depth"], dtype=np.float32)
    height, width = depth.shape
    return GeometryFrame(
        depth=depth,
        normal=np.asarray(prediction["normal"], dtype=np.float32),
        validity=np.asarray(prediction["mask"], dtype=np.float32),
        intrinsics=_pixel_intrinsics(prediction["intrinsics"], (width, height)),
        points=(
            np.asarray(prediction["points"], dtype=np.float32)
            if include_points
            else None
        ),
    )


def infer(
    model_manager,
    parameters,
    image,
    *,
    include_points,
    cancel_check=None,
):
    """Infer an RGB image and return its geometry fields."""
    import numpy as np

    if cancel_check is not None:
        cancel_check()
    model, _load_ms = model_manager.get_session(parameters["model"], parameters["device"])
    prediction = model_adapter(parameters["model"]).infer(
        model,
        np.asarray(image, dtype=np.float32) / 255.0,
        int(parameters["resolution_level"]),
        release_memory=True,
        include_points=include_points,
    )
    return _geometry_frame(prediction, include_points)
