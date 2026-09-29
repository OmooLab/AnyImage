from ..media.input import open_image
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
    image_path,
    *,
    include_points,
    cancel_check=None,
):
    """Infer one image and return its geometry fields."""
    if cancel_check is not None:
        cancel_check()
    prediction = infer_one(model_manager, parameters, image_path, include_points=include_points)
    return _geometry_frame(prediction, include_points)


def infer_one(
    model_manager,
    parameters,
    image_path,
    *,
    release_memory=True,
    include_points=True,
):
    import numpy as np

    model, _load_ms = model_manager.get_session(parameters["model"], parameters["device"])
    with open_image(image_path) as opened:
        image = np.asarray(opened.convert("RGB"), dtype=np.float32) / 255.0
    return model_adapter(parameters["model"]).infer(
        model,
        image,
        int(parameters["resolution_level"]),
        release_memory=release_memory,
        include_points=include_points,
    )
