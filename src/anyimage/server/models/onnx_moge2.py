"""MoGe-2 ONNX inference and NumPy post-processing."""

from pathlib import Path

from .onnx_runtime import create_session as create_runtime_session
from .onnx_runtime import run_session
from .moge_geometry import model_inputs, postprocess


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


def infer_normal(session, image, resolution_level):
    normal, = run_session(session, ["normal"], model_inputs(image, resolution_level))
    return normal[0]


def infer(session, image, resolution_level, *, fov_x=None, source_valid=None):
    output_names = {output.name for output in session.get_outputs()}
    scale_name = "metric_scale" if "metric_scale" in output_names else "scale"
    names = ("points", "normal", "mask", scale_name)
    values = run_session(
        session,
        list(names),
        model_inputs(image, resolution_level),
    )
    raw_output = dict(zip(names, values))
    raw_output["metric_scale"] = raw_output.pop(scale_name)
    return postprocess(
        raw_output, fov_x=fov_x, source_valid=source_valid,
    )
