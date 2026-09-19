"""Tiled ONNX inference shared by the Upscale models."""

from pathlib import Path

try:
    from .onnx_runtime import create_session as create_runtime_session
    from .onnx_runtime import run_session
except ImportError:
    from onnx_runtime import create_session as create_runtime_session
    from onnx_runtime import run_session


SCALE = 4
TILE_SIZE = 256
TILE_BORDER = 16
RESOURCE_ERROR_TOKENS = (
    "out of memory",
    "bad allocation",
    "bad_alloc",
    "failed to allocate",
    "not enough memory",
    "insufficient memory",
)


class UpscaleResourceError(RuntimeError):
    """The execution provider could not allocate resources for one tile."""


def create_session(model_directory, requested_device="auto"):
    paths = tuple(Path(model_directory).glob("*.onnx"))
    if len(paths) != 1:
        raise RuntimeError(
            f"Expected exactly one ONNX model in {model_directory}, found {len(paths)}"
        )
    path = paths[0]
    return create_runtime_session(path, requested_device)


def preprocess(image):
    import numpy as np

    image_array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return np.ascontiguousarray(image_array.transpose(2, 0, 1)[None])


def _run(session, input_tensor, *, release_memory=True):
    import numpy as np

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    try:
        raw_prediction = run_session(
            session,
            [output_name],
            {input_name: input_tensor},
            release_memory=release_memory,
        )[0]
    except (MemoryError, UnicodeDecodeError) as error:
        raise UpscaleResourceError(
            "the ONNX execution provider failed, usually because GPU or "
            "system memory was exhausted"
        ) from error
    except RuntimeError as error:
        if any(token in str(error).lower() for token in RESOURCE_ERROR_TOKENS):
            raise UpscaleResourceError(
                "the ONNX execution provider failed because GPU or system "
                "memory was exhausted"
            ) from error
        raise
    prediction = np.asarray(raw_prediction, dtype=np.float32)
    expected_shape = (
        1,
        3,
        input_tensor.shape[2] * SCALE,
        input_tensor.shape[3] * SCALE,
    )
    if prediction.shape != expected_shape:
        raise RuntimeError(
            f"Upscale model returned an unexpected output shape: {prediction.shape}"
        )
    if not np.isfinite(prediction).all():
        raise RuntimeError("Upscale model returned non-finite pixels")
    return prediction


def _prediction_pixels(prediction):
    import numpy as np

    pixels = np.clip(prediction[0].transpose(1, 2, 0), 0.0, 1.0)
    return np.rint(pixels * 255.0).astype(np.uint8)


def _pad_source(source, extra_height, extra_width, tile_border):
    import numpy as np

    mode = "reflect" if source.shape[0] > 1 and source.shape[1] > 1 else "edge"
    return np.pad(
        source,
        (
            (tile_border, tile_border + extra_height),
            (tile_border, tile_border + extra_width),
            (0, 0),
        ),
        mode=mode,
    )


def infer(session, image, cancel_check=None, *, release_memory=True, tile_border=TILE_BORDER):
    import numpy as np
    from PIL import Image

    try:
        source = np.asarray(image.convert("RGB"), dtype=np.uint8)
        height, width = source.shape[:2]
        if not 0 <= tile_border < TILE_SIZE // 2:
            raise ValueError("Invalid upscale tile border")
        core_size = TILE_SIZE - 2 * tile_border
        extra_height = (-height) % core_size
        extra_width = (-width) % core_size
        padded = _pad_source(source, extra_height, extra_width, tile_border)
        output = np.empty((height * SCALE, width * SCALE, 3), dtype=np.uint8)
        for top in range(0, height, core_size):
            core_height = min(core_size, height - top)
            for left in range(0, width, core_size):
                core_width = min(core_size, width - left)
                if cancel_check is not None and cancel_check():
                    raise RuntimeError("Task cancelled")
                tile = Image.fromarray(
                    padded[top : top + TILE_SIZE, left : left + TILE_SIZE],
                    mode="RGB",
                )
                final_tile = (
                    release_memory
                    and top + core_size >= height
                    and left + core_size >= width
                )
                pixels = _prediction_pixels(
                    _run(
                        session,
                        preprocess(tile),
                        release_memory=final_tile,
                    )
                )
                border = tile_border * SCALE
                output[
                    top * SCALE : (top + core_height) * SCALE,
                    left * SCALE : (left + core_width) * SCALE,
                ] = pixels[
                    border : border + core_height * SCALE,
                    border : border + core_width * SCALE,
                ]
        return Image.fromarray(output, mode="RGB")
    except UpscaleResourceError:
        raise
    except MemoryError as error:
        raise UpscaleResourceError(
            "the complete upscale result exceeded available system memory"
        ) from error
