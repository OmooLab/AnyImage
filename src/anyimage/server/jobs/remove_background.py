import time

from ..media.input import open_image, validate_input_path
from ..model_catalog import BACKGROUND_MODELS
from ..models.background import infer_alpha, infer_foreground, inference_device


def run(context, parameters):
    """Write foreground images or continuous alpha into the Job directory."""
    total_started = time.perf_counter()
    if parameters["model"] not in BACKGROUND_MODELS:
        raise ValueError(f"Unknown background removal model: {parameters['model']}")
    context.progress(0.02, "Starting Environment")
    context.check_cancelled()

    output_directory = context.directory
    output_directory.mkdir(parents=True, exist_ok=True)
    device = parameters["device"]
    model_manager = context.resource("model_manager")
    model_directory = model_manager.directory(parameters["model"])
    device = inference_device(model_directory, device)
    output_kind = parameters.get("output_kind", "foreground")
    if output_kind not in {"foreground", "alpha"}:
        raise ValueError(f"Unknown background removal output: {output_kind}")

    input_path = validate_input_path(parameters["input"])
    context.progress(0.12, f"Loading {parameters['model']} for {device.upper()}")
    if output_kind == "alpha":
        import numpy as np

        with open_image(input_path) as source:
            alpha, load_ms, inference_ms = infer_alpha(
                source, model_directory, device, model_cache=model_manager,
                cancel_check=context.check_cancelled,
            )
        context.check_cancelled()
        np.save(output_directory / "alpha.npy", alpha, allow_pickle=False)
    else:
        context.progress(0.35, "Removing background")
        foreground, load_ms, inference_ms = infer_foreground(
            input_path,
            model_directory,
            device,
            model_cache=model_manager,
            cancel_check=context.check_cancelled,
            preserve_input_alpha=True,
        )
        context.check_cancelled()
        context.progress(0.92, "Writing transparent PNG")
        output_path = output_directory / "foreground.png"
        foreground.convert("RGBA").save(
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
    context.progress(1.0, message)
    return {"alpha": "alpha.npy"} if output_kind == "alpha" else {"foreground": "foreground.png"}
