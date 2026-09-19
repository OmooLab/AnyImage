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

    from .onnx_upscale import UpscaleResourceError, infer

    if parameters["model"] not in UPSCALE_MODELS:
        raise ValueError(f"Unknown upscale model: {parameters['model']}")

    model_directory = model_manager.directory(parameters["model"])
    model = model_manager.get_upscale(
        model_directory,
        parameters["device"],
    )
    try:
        with open_image(image_path) as opened:
            source = limit_image(
                opened,
                parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
            )
            source_alpha = _source_alpha(source)
            prediction = infer(
                model,
                source,
                cancel_check=cancel_check,
                release_memory=release_memory,
                tile_border=48 if parameters["model"] == "HAT_GAN_X4_SHARPER" else 16,
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
    except (MemoryError, UnicodeDecodeError, UpscaleResourceError) as error:
        model_manager.release_upscale()
        device = str(parameters.get("device", "selected device")).upper()
        raise RuntimeError(
            f"Upscale could not finish on {device}: {error}. "
            "Reduce Maximum AI Input Size or select CPU, then try again."
        ) from error
