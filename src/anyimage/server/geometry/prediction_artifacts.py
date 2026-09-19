"""Export requested depth and normal artifacts from one MoGe prediction."""

from ..media.input import open_image
from ..media import DEFAULT_MAX_AI_INPUT_SIZE, limit_image
from ..models import moge
from .depth_texture import (
    write_depth_metadata,
    write_depth_texture,
)
from .normal_texture import write_camera_normal_texture


def _limited_model_input(source_path, output_path, max_input_size):
    with open_image(source_path) as opened:
        limited = limit_image(opened.convert("RGB"), max_input_size)
        limited.save(output_path, format="PNG", compress_level=1)
    return output_path


def _image_alpha(image_path, shape):
    import numpy as np
    from PIL import Image

    with open_image(image_path) as opened:
        alpha = opened.convert("RGBA").getchannel("A")
    alpha = alpha.resize(
        (int(shape[1]), int(shape[0])),
        Image.Resampling.NEAREST,
    )
    return np.asarray(alpha, dtype=np.float32) / 255.0


def _write_normal(frame, color_path, output_path, normal_mode):
    valid = _image_alpha(color_path, frame.depth.shape) >= 0.1
    with open_image(color_path) as source:
        output_size = source.size
    return write_camera_normal_texture(
        frame,
        valid,
        (0, 0),
        output_size,
        output_size,
        output_path,
        normal_mode=normal_mode,
    )


def generate_moge_artifacts(
    context,
    parameters,
    input_path,
    *,
    generate_depth=False,
    normal_mode="NONE",
):
    """Run MoGe once and write only the requested file artifacts."""
    normal_mode = str(normal_mode).upper()
    if normal_mode not in {"NONE", "TANGENT", "OBJECT"}:
        raise ValueError(f"Unsupported normal mode: {normal_mode}")
    model_path = _limited_model_input(
        input_path,
        context.directory / "model-input.png",
        parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
    )
    try:
        frame = moge.infer(
            context.resource("model_manager"),
            parameters,
            model_path,
            include_points=generate_depth,
            cancel_check=context.check_cancelled,
        )
        result = {}
        if generate_depth:
            context.progress(0.45, "Generating depth texture")
            alpha = _image_alpha(input_path, frame.depth.shape)
            result["depth"] = write_depth_texture(
                frame, context.directory / "depth.exr", alpha=alpha,
            )
            result["depth_metadata"] = write_depth_metadata(
                frame,
                context.directory / "depth.json",
            )

        if normal_mode != "NONE":
            context.progress(0.72, "Generating surface normal")
            key = f"{normal_mode.lower()}_normal"
            result[key] = _write_normal(
                frame,
                input_path,
                context.directory / f"{normal_mode.lower()}-normal.png",
                normal_mode,
            )
        return result
    finally:
        if model_path != input_path:
            model_path.unlink(missing_ok=True)
