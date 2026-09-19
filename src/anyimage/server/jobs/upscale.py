from ..media import DEFAULT_MAX_AI_INPUT_SIZE
from ..media.input import validate_input_path
from ..models.upscale import infer_one


def run(context, parameters):
    context.log(
        f"Upscale model: {parameters['model']}; "
        f"maximum AI input size: "
        f"{parameters.get('max_input_size', DEFAULT_MAX_AI_INPUT_SIZE)} px"
    )
    context.progress(0.02, "Preparing upscale input")
    context.check_cancelled()
    input_path = validate_input_path(parameters["input"])
    context.directory.mkdir(parents=True, exist_ok=True)
    context.progress(0.08, "Upscaling image")
    prediction = infer_one(
        context.resource("model_manager"),
        parameters,
        input_path,
        cancel_check=context.check_cancelled,
    )
    context.check_cancelled()
    prediction.save(context.directory / "upscale.png", format="PNG", compress_level=1)
    context.progress(1.0, "Image upscale complete")
    return {"upscale": "upscale.png"}
