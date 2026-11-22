"""Generate optional AI files from one rectangular Cutout image input."""

from ..geometry.prediction_artifacts import generate_moge_artifacts


def run(context, parameters):
    context.progress(0.05, "Preparing Cutout Selection")
    context.directory.mkdir(parents=True, exist_ok=True)
    result = generate_moge_artifacts(
        context, parameters,
        generate_depth=parameters["generate_depth"], normal_space="OBJECT",
    )
    context.check_cancelled()
    context.progress(1.0, "Cutout artifacts are ready")
    return result
