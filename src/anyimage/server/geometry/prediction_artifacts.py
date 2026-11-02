"""Export requested depth and normal artifacts from one MoGe prediction."""

from ..media.input import open_image
from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, limit_image
from ..models.geometry import infer_geometry
from .depth_texture import (
    write_depth_metadata,
    write_depth_texture,
)
from .normal_texture import write_normal_texture


def generate_moge_artifacts(
    context,
    parameters,
    input_path,
    *,
    generate_depth=False,
    generate_normal=False,
    normal_space="TANGENT",
):
    """Run MoGe once and write only the requested file artifacts."""
    import numpy as np
    from PIL import Image

    with open_image(input_path) as source:
        model_image = limit_image(
            source.convert("RGB"),
            parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
        )
        source_alpha = source.convert("RGBA").getchannel("A")
        output_size = source.size
    frame = infer_geometry(
        context.resource("model_manager"),
        parameters,
        model_image,
        include_points=generate_depth,
        cancel_check=context.check_cancelled,
    )
    height, width = frame.depth.shape
    alpha = np.asarray(
        source_alpha.resize((width, height), Image.Resampling.NEAREST),
        dtype=np.float32,
    ) / 255.0
    result = {}
    if generate_depth:
        context.progress(0.45, "Generating depth texture")
        result["depth"] = write_depth_texture(
            frame, context.directory / "depth.exr", alpha=alpha,
        )
        result["depth_metadata"] = write_depth_metadata(
            frame, context.directory / "depth.json",
        )
    if generate_normal:
        context.progress(0.72, "Generating surface normal")
        normal_name = f"{normal_space.lower()}_normal"
        result[normal_name] = write_normal_texture(
            frame,
            alpha >= 0.1,
            output_size,
            context.directory / f"{normal_name.replace('_', '-')}.png",
            normal_space=normal_space,
        )
    return result
