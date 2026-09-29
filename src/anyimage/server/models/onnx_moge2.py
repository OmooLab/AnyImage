"""MoGe-2 ONNX inference and NumPy post-processing."""

from pathlib import Path

from .onnx_runtime import create_session as create_runtime_session
from .onnx_runtime import run_session
from .moge_geometry import MIN_TOKENS, MAX_TOKENS, postprocess


ONNX_FILENAME = "model.onnx"
COREML_PROVIDER_OPTIONS = {
    "RequireStaticInputShapes": "1",
}


def create_session(model_directory, requested_device="auto"):
    path = Path(model_directory) / ONNX_FILENAME
    return create_runtime_session(
        path,
        requested_device,
        coreml_options=COREML_PROVIDER_OPTIONS,
    )


def infer(
    session, image, resolution_level, *, release_memory=True,
    fov_x=None, source_valid=None, include_points=True,
):
    import numpy as np

    level = min(max(int(resolution_level), 0), 9)
    num_tokens = int(MIN_TOKENS + level / 9.0 * (MAX_TOKENS - MIN_TOKENS))
    image_input = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32)
    input_feed = {
        "image": image_input,
        "num_tokens": np.asarray(num_tokens, dtype=np.int64),
    }
    output_names = {output.name for output in session.get_outputs()}
    scale_name = "metric_scale" if "metric_scale" in output_names else "scale"
    names = ("points", "normal", "mask", scale_name)
    values = run_session(
        session,
        list(names),
        input_feed,
        release_memory=release_memory,
    )
    raw_output = dict(zip(names, values))
    raw_output["metric_scale"] = raw_output.pop(scale_name)
    return postprocess(
        raw_output, fov_x=fov_x, source_valid=source_valid,
        include_points=include_points,
    )
