"""BiRefNet probability alpha with official RGB normalization."""

from pathlib import Path

from .onnx_runtime import create_session as create_runtime_session
from .onnx_runtime import run_session


def create_session(model_directory, requested_device="auto"):
    return create_runtime_session(Path(model_directory) / "model.onnx", requested_device)


def preprocess(image, size):
    import numpy as np
    from PIL import Image

    resized = image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    array = (array - np.array((0.485, 0.456, 0.406), dtype=np.float32)) / np.array(
        (0.229, 0.224, 0.225), dtype=np.float32,
    )
    return np.ascontiguousarray(array.transpose(2, 0, 1)[None])


def infer_alpha(session, image, *, release_memory=True):
    import numpy as np
    from PIL import Image

    input_spec = session.get_inputs()[0]
    size = input_spec.shape[-1]
    if size not in (1024, 2048) or input_spec.shape != [1, 3, size, size]:
        raise RuntimeError("BiRefNet returned an invalid input contract")
    alpha = np.asarray(run_session(
        session, [session.get_outputs()[0].name],
        {input_spec.name: preprocess(image, size)}, release_memory=release_memory,
    )[0], dtype=np.float32)
    if (alpha.shape != (1, 1, size, size) or not np.isfinite(alpha).all()
            or alpha.min() < 0 or alpha.max() > 1):
        raise RuntimeError("BiRefNet returned an invalid alpha mask")
    mask = Image.fromarray(alpha[0, 0]).resize(image.size, Image.Resampling.BILINEAR)
    return np.clip(np.asarray(mask, dtype=np.float32), 0.0, 1.0)
