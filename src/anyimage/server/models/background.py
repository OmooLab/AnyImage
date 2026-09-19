import time
from importlib import import_module
from pathlib import Path

from ..media import check_cancelled
from ..media.input import open_image, validate_input_path


def inference_device(model_dir, requested_device):
    if Path(model_dir).name == "birefnet-hr-matting":
        return "cpu"
    return getattr(requested_device, "type", requested_device)


def model_adapter(model_dir):
    name = Path(model_dir).name
    if name == "BEN2-ONNX":
        return import_module(".onnx_ben2", __package__)
    if name in {"birefnet-lite", "birefnet-hr-matting"}:
        return import_module(".onnx_birefnet", __package__)
    raise ValueError(f"Unknown background model directory: {name}")


def infer_alpha(
    image,
    model_dir,
    device,
    model_cache=None,
    cancel_check=None,
    release_memory=True,
):
    from PIL import Image

    check_cancelled(cancel_check)
    adapter = model_adapter(model_dir)

    owns_model = model_cache is None
    requested_device = inference_device(model_dir, device)
    if owns_model:
        load_started = time.perf_counter()
        model = adapter.create_session(model_dir, requested_device)
        load_ms = (time.perf_counter() - load_started) * 1000.0
    else:
        model, load_ms = model_cache.get_background(model_dir, requested_device)

    check_cancelled(cancel_check)
    source_rgba = image.convert("RGBA")
    image = Image.new("RGB", source_rgba.size, (0, 0, 0))
    image.paste(
        source_rgba.convert("RGB"),
        (0, 0),
        source_rgba.getchannel("A"),
    )
    inference_started = time.perf_counter()
    alpha = adapter.infer_alpha(
        model,
        image,
        release_memory=release_memory,
    )
    inference_ms = (time.perf_counter() - inference_started) * 1000.0
    check_cancelled(cancel_check)
    return alpha, load_ms, inference_ms


def infer_foreground(
    input_path,
    model_dir,
    device,
    model_cache=None,
    cancel_check=None,
    preserve_input_alpha=False,
    release_memory=True,
):
    import numpy as np
    from PIL import Image, ImageChops

    check_cancelled(cancel_check)
    input_path = validate_input_path(Path(input_path))
    with open_image(input_path) as opened_image:
        source = opened_image.convert("RGBA")
    alpha, load_ms, inference_ms = infer_alpha(
        source, model_dir, device, model_cache=model_cache,
        cancel_check=cancel_check, release_memory=release_memory,
    )
    mask = Image.fromarray((alpha * 255).astype(np.uint8))
    if preserve_input_alpha:
        foreground = source
        mask = ImageChops.multiply(source.getchannel("A"), mask)
    else:
        foreground = Image.new("RGBA", source.size, (0, 0, 0, 255))
        foreground.paste(source.convert("RGB"), (0, 0), source.getchannel("A"))
    foreground.putalpha(mask)
    return foreground, load_ms, inference_ms
