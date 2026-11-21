"""Generate optional AI files from one rectangular Cutout image input."""

from ..media.input import validate_input_path

from ..geometry.prediction_artifacts import generate_moge_artifacts


def run(context, parameters):
    context.progress(0.05, "Preparing Cutout Selection")
    context.directory.mkdir(parents=True, exist_ok=True)
    input_path = validate_input_path(parameters["input"])
    artifacts = generate_moge_artifacts(
        context, parameters, input_path,
        generate_depth=parameters["generate_depth"], normal_space="OBJECT",
    )
    context.check_cancelled()
    context.progress(1.0, "Cutout artifacts are ready")
    return {key: path.name for key, path in artifacts.items()}
