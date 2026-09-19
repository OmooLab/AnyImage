"""Generate model-space depth and normals for one complete image."""

from ..geometry.prediction_artifacts import generate_moge_artifacts
from ..media.input import validate_input_path


def run(context, parameters):
    plane_type = parameters["plane_type"]
    if plane_type not in {"DEPTH", "RELIEF"}:
        raise ValueError(f"Unsupported plane type: {plane_type}")
    context.progress(0.05, "Preparing depth conversion")
    context.directory.mkdir(parents=True, exist_ok=True)
    input_path = validate_input_path(parameters["input"])
    artifacts = generate_moge_artifacts(
        context,
        parameters,
        input_path,
        generate_depth=True,
        normal_mode="OBJECT" if plane_type == "DEPTH" else "TANGENT",
    )
    context.check_cancelled()
    context.progress(1.0, "Depth conversion data is ready")
    return {key: path.name for key, path in artifacts.items()}
