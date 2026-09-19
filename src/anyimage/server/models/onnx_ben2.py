"""BEN2 ONNX inference with Pillow and NumPy preprocessing."""

from pathlib import Path

try:
    from .onnx_runtime import create_session as create_runtime_session
    from .onnx_runtime import run_session
except ImportError:
    from onnx_runtime import create_session as create_runtime_session
    from onnx_runtime import run_session


ONNX_PATH = Path("onnx/model_fp16.onnx")
INPUT_SIZE = (1024, 1024)


def model_path(model_directory):
    return Path(model_directory) / ONNX_PATH


def create_session(model_directory, requested_device="auto"):
    return create_runtime_session(model_path(model_directory), requested_device)


def preprocess(image):
    import numpy as np
    from PIL import Image

    resized = image.convert("RGB").resize(INPUT_SIZE, Image.Resampling.LANCZOS)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    mean = np.array((0.485, 0.456, 0.406), dtype=np.float32)
    std = np.array((0.229, 0.224, 0.225), dtype=np.float32)
    array = (array - mean) / std
    return np.ascontiguousarray(array.transpose(2, 0, 1)[None])


def infer_alpha(session, image, *, release_memory=True):
    import numpy as np
    from PIL import Image

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    alpha = run_session(
        session,
        [output_name],
        {input_name: preprocess(image)},
        release_memory=release_memory,
    )[0]
    alpha = np.asarray(alpha, dtype=np.float32)
    if (alpha.ndim != 4 or alpha.shape[:2] != (1, 1)
            or not all(alpha.shape[2:]) or not np.isfinite(alpha).all()):
        raise RuntimeError("BEN2 returned an invalid alpha mask")
    alpha = alpha[0, 0]
    minimum = float(alpha.min())
    span = max(float(alpha.max()) - minimum, np.finfo(np.float32).eps)
    alpha = np.clip((alpha - minimum) / span, 0.0, 1.0)
    mask = Image.fromarray(alpha)
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    return np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0)
