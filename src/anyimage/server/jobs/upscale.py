from ..media.input import DEFAULT_MAX_AI_INPUT_SIZE, limit_image, load_ai_input
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
    context.directory.mkdir(parents=True, exist_ok=True)
    context.progress(0.08, "Upscaling image")
    if parameters["model"] not in UPSCALE_MODELS:
        raise ValueError(f"Unknown upscale model: {parameters['model']}")
    source = Image.fromarray(load_ai_input(parameters["input"], as_bytes=True))
    source = limit_image(source, parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE))
    model, _load_ms = context.resource("model_manager").get_session(
        parameters["model"], parameters["device"],
    )
    prediction = model_adapter(parameters["model"]).infer(
        model, source, cancel_check=context.check_cancelled,
        tile_border=UPSCALE_MODELS[parameters["model"]].tile_border,
    )
    size = (source.width * 2, source.height * 2)
    prediction = prediction.resize(size, Image.Resampling.LANCZOS)
    prediction.putalpha(source.getchannel("A").resize(size, Image.Resampling.LANCZOS))
    context.check_cancelled()
    prediction.save(context.directory / "upscale.png", format="PNG", compress_level=1)
    context.progress(1.0, "Image upscale complete")
    return {"upscale": "upscale.png"}
