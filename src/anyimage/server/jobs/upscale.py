from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, limit_image
from ..media.input import open_image, validate_input_path
from ..model_catalog import UPSCALE_MODELS
from ..models import model_adapter


def run(context, parameters):
    """Upscale one image to twice its size and preserve its alpha."""
    from PIL import Image

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
    if parameters["model"] not in UPSCALE_MODELS:
        raise ValueError(f"Unknown upscale model: {parameters['model']}")
    model, _load_ms = context.resource("model_manager").get_session(
        parameters["model"], parameters["device"],
    )
    with open_image(input_path) as opened:
        source = limit_image(
            opened,
            parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
        )
        source_alpha = (
            source.convert("RGBA").getchannel("A")
            if "A" in source.getbands() or "transparency" in source.info
            else None
        )
        prediction = model_adapter(parameters["model"]).infer(
            model,
            source,
            cancel_check=context.check_cancelled,
            tile_border=UPSCALE_MODELS[parameters["model"]].tile_border,
        )
        prediction = prediction.resize(
            (source.width * 2, source.height * 2), Image.Resampling.LANCZOS,
        )
        if source_alpha is not None:
            prediction = prediction.convert("RGBA")
            prediction.putalpha(source_alpha.resize(prediction.size, Image.Resampling.LANCZOS))
    context.check_cancelled()
    prediction.save(context.directory / "upscale.png", format="PNG", compress_level=1)
    context.progress(1.0, "Image upscale complete")
    return {"upscale": "upscale.png"}
