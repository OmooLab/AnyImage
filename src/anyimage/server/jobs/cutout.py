"""Generate optional AI files from one rectangular Cutout image input."""

from ..media.input import validate_input_path

from ..geometry.prediction_artifacts import generate_moge_artifacts


def run(context, parameters):
    context.progress(0.05, "Preparing Cutout Selection")
    context.directory.mkdir(parents=True, exist_ok=True)
    input_path = validate_input_path(parameters["input"])
    result = {}
    generate_depth = bool(parameters.get("generate_depth", False))
    normal_mode = str(parameters.get("normal_mode", "NONE"))
    if generate_depth or normal_mode != "NONE":
        artifacts = generate_moge_artifacts(
            context,
            parameters,
            input_path,
            generate_depth=generate_depth,
            normal_mode=normal_mode,
        )
        result.update({key: path.name for key, path in artifacts.items()})
    context.check_cancelled()
    context.progress(1.0, "Cutout artifacts are ready")
    return result
