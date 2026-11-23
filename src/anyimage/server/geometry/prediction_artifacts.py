"""Export requested depth and normal artifacts from one MoGe prediction."""

from dataclasses import dataclass
from pathlib import Path

from ..media.exr import write_float_exr
from ..media.input import load_ai_input
from ..models import model_adapter


@dataclass
class GeometryFrame:
    depth: object
    validity: object
    intrinsics: object
    normal: object | None = None
    points: object | None = None

    def __post_init__(self):
        import numpy as np

        depth = np.asarray(self.depth)
        validity = np.asarray(self.validity)
        intrinsics = np.asarray(self.intrinsics)
        if depth.dtype != np.float32 or depth.ndim != 2:
            raise ValueError("Geometry depth must be a 2D float32 field")
        if validity.dtype != np.float32 or validity.shape != depth.shape:
            raise ValueError("Geometry validity must match the depth as float32")
        if intrinsics.dtype != np.float32 or intrinsics.shape != (3, 3):
            raise ValueError("Geometry intrinsics must be a 3x3 float32 matrix")
        for name in ("normal", "points"):
            value = getattr(self, name)
            if value is None:
                continue
            field = np.asarray(value)
            if field.dtype != np.float32 or field.shape != (*depth.shape, 3):
                raise ValueError(
                    f"Geometry {name} must match the depth as three-channel float32"
                )


def _pixel_intrinsics(intrinsics, image_size):
    import numpy as np

    width, height = image_size
    result = np.asarray(intrinsics, dtype=np.float32).copy()
    result[0] *= width
    result[1] *= height
    result[2] = (0.0, 0.0, 1.0)
    return result


def infer_geometry(adapter, session, rgb, resolution_level, **options):
    """Infer full geometry with camera intrinsics expressed in pixels."""
    import numpy as np

    prediction = adapter.infer(session, rgb, resolution_level, **options)
    depth = np.asarray(prediction["depth"], dtype=np.float32)
    height, width = depth.shape
    return GeometryFrame(
        depth=depth,
        normal=np.asarray(prediction["normal"], dtype=np.float32),
        validity=np.asarray(prediction["mask"], dtype=np.float32),
        intrinsics=_pixel_intrinsics(prediction["intrinsics"], (width, height)),
        points=np.asarray(prediction["points"], dtype=np.float32),
    )


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

    rgba = load_ai_input(parameters["input"])
    rgb = rgba[..., :3]
    context.check_cancelled()
    model = parameters["model"]
    adapter = model_adapter(model)
    session, _ = context.resource("model_manager").get_session(model, parameters["device"])
    level = int(parameters["resolution_level"])
    if generate_depth:
        options = {"refine_steps": parameters["refine_steps"]} if "refine_steps" in parameters else {}
        frame = infer_geometry(adapter, session, rgb, level, **options)
        normal = frame.normal
    else:
        normal = adapter.infer_normal(session, rgb, level)

    height, width = normal.shape[:2]
    alpha = np.asarray(Image.fromarray(rgba[..., 3]).resize((width, height), Image.Resampling.NEAREST))
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
        normal, alpha >= 0.1, tuple(parameters["output_size"]),
        context.directory / f"{normal_name.replace('_', '-')}.png",
        normal_space=normal_space,
    ).name
    return result


def write_depth_texture(frame, output_path, *, alpha):
    """Write camera-space XYZ and alpha-weighted model validity as float RGBA."""
    import numpy as np

    if frame.points is None:
        raise ValueError("Depth requires a point field")
    points = np.asarray(frame.points, dtype=np.float32)
    validity = np.asarray(frame.validity, dtype=np.float32)
    alpha = np.asarray(alpha, dtype=np.float32)
    if alpha.shape != validity.shape:
        raise ValueError("Depth Alpha must match the validity dimensions")
    if not np.isfinite(points).all():
        raise ValueError("Point field contains non-finite values")
    if not np.any((validity > 0.5) & np.isfinite(frame.depth) & (frame.depth > 0)):
        raise ValueError("Geometry frame contains no valid depth pixels")
    rgba = np.empty((*validity.shape, 4), dtype=np.float32)
    rgba[..., :3] = points
    rgba[..., 3] = alpha * validity
    return write_float_exr(rgba, output_path)


def write_normal_texture(normal, visibility, output_size, output_path, *, normal_space="TANGENT"):
    """Encode camera normals in flat tangent or image-object space."""
    import numpy as np
    from PIL import Image

    normal = np.asarray(normal, dtype=np.float32)
    if not np.isfinite(normal).all():
        raise ValueError("Normal field contains non-finite values")
    if normal_space == "OBJECT":
        converted = normal[..., (0, 2, 1)] * np.asarray((1.0, 1.0, -1.0), dtype=np.float32)
        empty_normal = (128, 0, 128)
    elif normal_space == "TANGENT":
        converted = normal * np.asarray((1.0, -1.0, -1.0), dtype=np.float32)
        empty_normal = (128, 128, 255)
    else:
        raise ValueError(f"Unsupported normal space: {normal_space}")
    encoded = np.clip((converted + 1.0) * 127.5, 0.0, 255.0).astype(np.uint8)
    encoded[~visibility] = empty_normal
    image = Image.fromarray(encoded, mode="RGB")
    if image.size != output_size:
        image = image.resize(output_size, Image.Resampling.BILINEAR)
    output_path = Path(output_path)
    image.save(output_path)
    return output_path
