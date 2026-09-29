from ..media.input import open_image
from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, limit_image
from ..model_catalog import UPSCALE_MODELS


def _source_alpha(image):
    if "A" not in image.getbands() and "transparency" not in image.info:
        return None
    return image.convert("RGBA").getchannel("A")


def infer_one(
    model_manager,
    parameters,
    image_path,
    cancel_check=None,
    release_memory=True,
):
    from PIL import Image

    from . import model_adapter

    if parameters["model"] not in UPSCALE_MODELS:
        raise ValueError(f"Unknown upscale model: {parameters['model']}")

    model, _load_ms = model_manager.get_session(parameters["model"], parameters["device"])
    with open_image(image_path) as opened:
        source = limit_image(
            opened,
            parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
        )
        source_alpha = _source_alpha(source)
        prediction = model_adapter(parameters["model"]).infer(
            model,
            source,
            cancel_check=cancel_check,
            release_memory=release_memory,
            tile_border=UPSCALE_MODELS[parameters["model"]].tile_border,
        )
        prediction = prediction.resize(
            (source.width * 2, source.height * 2),
            Image.Resampling.LANCZOS,
        )
        if source_alpha is None:
            return prediction
        alpha = source_alpha.resize(
            prediction.size,
            Image.Resampling.LANCZOS,
        )
        prediction = prediction.convert("RGBA")
        prediction.putalpha(alpha)
        return prediction
