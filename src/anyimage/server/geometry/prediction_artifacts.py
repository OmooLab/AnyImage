"""Export requested depth and normal artifacts from one MoGe prediction."""

from ..media.input import open_image
from ..media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, limit_image
from ..models import model_adapter
from ..models.geometry import infer_geometry
from .depth_texture import write_depth_texture
from .normal_texture import write_normal_texture


def generate_moge_artifacts(
    context,
    parameters,
    *,
    generate_depth,
    normal_space="TANGENT",
):
    """Run MoGe once and write only the requested file artifacts."""
    import numpy as np
    from PIL import Image

    with open_image(parameters["input"]) as source:
        model_image = limit_image(
            source.convert("RGB"),
            parameters.get("max_input_size", DEFAULT_MAX_AI_INPUT_SIZE),
        )
        source_alpha = source.convert("RGBA").getchannel("A")
        output_size = source.size
    context.check_cancelled()
    model = parameters["model"]
    adapter = model_adapter(model)
    session, _ = context.resource("model_manager").get_session(model, parameters["device"])
    rgb = np.asarray(model_image, dtype=np.float32) / 255.0
    level = int(parameters["resolution_level"])
    if generate_depth:
        options = {"refine_steps": parameters["refine_steps"]} if "refine_steps" in parameters else {}
        frame = infer_geometry(adapter, session, rgb, level, **options)
        normal = frame.normal
    else:
        normal = adapter.infer_normal(session, rgb, level)

    height, width = normal.shape[:2]
    alpha = np.asarray(
        source_alpha.resize((width, height), Image.Resampling.NEAREST),
        dtype=np.float32,
    ) / 255.0
    result = {}
    if generate_depth:
        context.progress(0.45, "Generating depth texture")
        intrinsics = frame.intrinsics
        if not np.isfinite(intrinsics).all() or intrinsics[0, 0] <= 0 or intrinsics[1, 1] <= 0:
            raise ValueError("Invalid camera intrinsics")
        result["intrinsics"] = intrinsics.tolist()
        result["depth"] = write_depth_texture(frame, context.directory / "depth.exr", alpha=alpha).name
    context.progress(0.72, "Generating surface normal")
    normal_name = f"{normal_space.lower()}_normal"
    result[normal_name] = write_normal_texture(
        normal, alpha >= 0.1, output_size,
        context.directory / f"{normal_name.replace('_', '-')}.png",
        normal_space=normal_space,
    ).name
    return result
