import time

from ..media.input import open_image, validate_input_path
from ..model_catalog import BACKGROUND_MODELS
from ..models import model_adapter


def run(context, parameters):
    """Write foreground images or continuous alpha into the Job directory."""
    import numpy as np
    from PIL import Image, ImageChops

    total_started = time.perf_counter()
    if parameters["model"] not in BACKGROUND_MODELS:
        raise ValueError(f"Unknown background removal model: {parameters['model']}")
    context.progress(0.02, "Starting Environment")
    context.check_cancelled()

    output_directory = context.directory
    output_directory.mkdir(parents=True, exist_ok=True)
    output_kind = parameters.get("output_kind", "foreground")
    if output_kind not in {"foreground", "alpha"}:
        raise ValueError(f"Unknown background removal output: {output_kind}")

    input_path = validate_input_path(parameters["input"])
    context.progress(0.12, "Loading {model}", model=parameters["model"])
    with open_image(input_path) as opened:
        source = opened.convert("RGBA")
    context.check_cancelled()
    model, load_ms = context.resource("model_manager").get_session(
        parameters["model"], parameters["device"],
    )
    context.check_cancelled()
    model_image = Image.new("RGB", source.size, (0, 0, 0))
    model_image.paste(source.convert("RGB"), (0, 0), source.getchannel("A"))
    if output_kind == "foreground":
        context.progress(0.35, "Removing background")
    inference_started = time.perf_counter()
    alpha = model_adapter(parameters["model"]).infer_alpha(model, model_image)
    inference_ms = (time.perf_counter() - inference_started) * 1000.0
    context.check_cancelled()
    if output_kind == "alpha":
        np.save(output_directory / "alpha.npy", alpha, allow_pickle=False)
    else:
        mask = Image.fromarray((alpha * 255).astype(np.uint8))
        source.putalpha(ImageChops.multiply(source.getchannel("A"), mask))
        context.check_cancelled()
        context.progress(0.92, "Writing transparent PNG")
        output_path = output_directory / "foreground.png"
        source.save(
            output_path,
            format="PNG",
            compress_level=1,
        )
        if not output_path.is_file():
            raise RuntimeError("Background removal did not write a foreground image")

    context.check_cancelled()
    total_ms = (time.perf_counter() - total_started) * 1000.0
    message = (
        f"Background removed in {inference_ms:.0f} ms "
        f"(model load {load_ms:.0f} ms, total {total_ms:.0f} ms)"
    )
    context.log(message)
    context.progress(
        1.0,
        "Background removed in {inference} ms (model load {load} ms, total {total} ms)",
        inference=f"{inference_ms:.0f}", load=f"{load_ms:.0f}", total=f"{total_ms:.0f}",
    )
    return {"alpha": "alpha.npy"} if output_kind == "alpha" else {"foreground": "foreground.png"}
