from ..media.input import open_image
from .geometry import GeometryFrame


def _pixel_intrinsics(intrinsics, image_size):
    import numpy as np

    width, height = image_size
    result = np.asarray(intrinsics, dtype=np.float32).copy()
    if (
        0.0 <= float(result[0, 2]) <= 1.0
        and 0.0 <= float(result[1, 2]) <= 1.0
    ):
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
    prediction = infer_one(model_manager, parameters, image_path)
    return _geometry_frame(prediction, include_points)


def infer_one(
    model_manager,
    parameters,
    image_path,
    *,
    release_memory=True,
):
    import numpy as np

    model_directory = model_manager.directory(parameters["model"])
    model = model_manager.get_moge(
        model_directory,
        parameters["device"],
    )
    with open_image(image_path) as opened:
        image = np.asarray(opened.convert("RGB"), dtype=np.float32) / 255.0
    return infer_image(
        model,
        image,
        int(parameters["resolution_level"]),
        release_memory=release_memory,
    )


def infer_image(session, image, resolution_level, **options):
    """Dispatch one RGB array to the selected MoGe ONNX model."""
    from . import onnx_moge2, onnx_moge3

    backend = onnx_moge3 if isinstance(session, onnx_moge3.Moge3Session) else onnx_moge2
    return backend.infer(session, image, resolution_level, **options)
