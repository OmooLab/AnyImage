import time

from ..media.input import load_ai_input
from ..model_catalog import BACKGROUND_MODELS
from ..models import model_adapter


def run(context, parameters):
    """Write the model opacity mask at the source resolution."""
    import numpy as np
    from PIL import Image

    total_started = time.perf_counter()
    if parameters["model"] not in BACKGROUND_MODELS:
        raise ValueError(f"Unknown background removal model: {parameters['model']}")
    context.progress(0.02, "Starting Environment")
    context.check_cancelled()

    output_directory = context.directory
    output_directory.mkdir(parents=True, exist_ok=True)
    context.progress(0.12, "Loading {model}", model=parameters["model"])
    rgba = load_ai_input(parameters["input"], as_bytes=True)
    rgba[..., :3][rgba[..., 3] == 0] = 0
    model_image = Image.fromarray(rgba[..., :3])
    del rgba
    context.check_cancelled()
    model, load_ms = context.resource("model_manager").get_session(
        parameters["model"], parameters["device"],
    )
    context.check_cancelled()
    context.progress(0.35, "Removing background")
    inference_started = time.perf_counter()
    alpha = model_adapter(parameters["model"]).infer_alpha(model, model_image)
    inference_ms = (time.perf_counter() - inference_started) * 1000.0
    context.check_cancelled()
    np.save(output_directory / "alpha.npy", alpha, allow_pickle=False)
    context.check_cancelled()
    total_ms = (time.perf_counter() - total_started) * 1000.0
    message = "Background removed in {inference} ms (model load {load} ms, total {total} ms)"
    timings = dict(inference=f"{inference_ms:.0f}", load=f"{load_ms:.0f}", total=f"{total_ms:.0f}")
    context.log(message.format(**timings))
    context.progress(1.0, message, **timings)
    return {"alpha": "alpha.npy"}
