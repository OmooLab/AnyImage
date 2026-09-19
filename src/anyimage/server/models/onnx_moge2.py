"""MoGe-2 ONNX inference and NumPy post-processing."""

from pathlib import Path

from .onnx_runtime import create_session as create_runtime_session
from .onnx_runtime import run_session


ONNX_FILENAME = "model.onnx"
MIN_TOKENS = 1200
MAX_TOKENS = 3600
COREML_PROVIDER_OPTIONS = {
    "RequireStaticInputShapes": "1",
}


def create_session(model_directory, requested_device="auto"):
    path = Path(model_directory) / ONNX_FILENAME
    return create_runtime_session(
        path,
        requested_device,
        coreml_options=COREML_PROVIDER_OPTIONS,
    )


def normalized_view_plane_uv(width, height, dtype):
    import numpy as np

    aspect_ratio = width / height
    span_x = aspect_ratio / (1.0 + aspect_ratio**2) ** 0.5
    span_y = 1.0 / (1.0 + aspect_ratio**2) ** 0.5
    u = np.linspace(
        -span_x * (width - 1) / width,
        span_x * (width - 1) / width,
        width,
        dtype=dtype,
    )
    v = np.linspace(
        -span_y * (height - 1) / height,
        span_y * (height - 1) / height,
        height,
        dtype=dtype,
    )
    u, v = np.meshgrid(u, v, indexing="xy")
    return np.stack((u, v), axis=-1)


def solve_focal_shift(uv, points):
    import numpy as np

    uv = uv.reshape(-1, 2)
    xy = points[..., :2].reshape(-1, 2)
    z = points[..., 2].reshape(-1)
    matrix = np.stack((xy, -uv), axis=-1).reshape(-1, 2)
    target = (uv * z[:, None]).reshape(-1)
    focal, shift = np.linalg.lstsq(matrix, target, rcond=None)[0]
    epsilon = np.finfo(np.float32).eps
    for _iteration in range(20):
        denominator = z + shift
        denominator = np.where(
            np.abs(denominator) < epsilon,
            np.copysign(epsilon, denominator),
            denominator,
        )
        projected = xy / denominator[:, None]
        residual = (focal * projected - uv).reshape(-1)
        jacobian = np.stack(
            (
                projected,
                -focal * xy / np.square(denominator)[:, None],
            ),
            axis=-1,
        ).reshape(-1, 2)
        delta = np.linalg.lstsq(jacobian, -residual, rcond=None)[0]
        focal += delta[0]
        shift += delta[1]
        if np.max(np.abs(delta)) < 1e-6:
            break
    return np.float32(focal), shift


def recover_focal_shift(points, mask, downsample_size=(64, 64)):
    import numpy as np

    height, width = points.shape[:2]
    uv = normalized_view_plane_uv(width, height, points.dtype)
    target_height, target_width = downsample_size
    y = np.floor(np.arange(target_height) * height / target_height).astype(int)
    x = np.floor(np.arange(target_width) * width / target_width).astype(int)
    points_low = points[y[:, None], x[None, :]]
    uv_low = uv[y[:, None], x[None, :]]
    mask_low = mask[y[:, None], x[None, :]]
    points_low = points_low[mask_low]
    uv_low = uv_low[mask_low]
    if len(points_low) < 2:
        return np.float32(1.0), np.float32(0.0)
    return solve_focal_shift(uv_low, points_low)


def depth_to_points(depth, intrinsics):
    import numpy as np

    height, width = depth.shape
    u = np.linspace(0.5 / width, 1.0 - 0.5 / width, width, dtype=depth.dtype)
    v = np.linspace(0.5 / height, 1.0 - 0.5 / height, height, dtype=depth.dtype)
    u, v = np.meshgrid(u, v, indexing="xy")
    x = (u - intrinsics[0, 2]) / intrinsics[0, 0] * depth
    y = (v - intrinsics[1, 2]) / intrinsics[1, 1] * depth
    return np.stack((x, y, depth), axis=-1)


def recover_known_fov_shift(points, mask, fx, fy):
    """Fit camera Z translation with fixed intrinsics on visible predictions."""
    import numpy as np
    from scipy.optimize import least_squares

    height, width = mask.shape
    intrinsics = np.array(((fx, 0, 0.5), (0, fy, 0.5), (0, 0, 1)))
    rays = depth_to_points(np.ones((height, width)), intrinsics)
    valid = (mask > 0.5) & np.isfinite(points).all(-1)
    if valid.sum() < 16:
        return 0.0, np.zeros_like(valid)
    stride = max(1, min(height, width) // 64)
    selected = valid[::stride, ::stride]
    p = points[::stride, ::stride][selected].astype(float)
    q = rays[::stride, ::stride, :2][selected]
    if len(p) < 2:
        p, q = points[valid].astype(float), rays[..., :2][valid]
    initial = np.sum(q * (p[:, :2] - q * p[:, 2:])) / max(np.sum(q * q), 1e-8)
    lower = -float(points[..., 2][valid].min()) + 1e-5
    fitted = least_squares(
        lambda shift: (p[:, :2] / (p[:, 2:] + shift[0]) - q).ravel(),
        [max(initial, lower + 1e-4)], bounds=([lower], [np.inf]),
    )
    return fitted.x[0], valid


def postprocess(raw_output, *, fov_x=None, source_valid=None):
    import numpy as np

    points = np.asarray(raw_output["points"][0], dtype=np.float32)
    normal = np.asarray(raw_output["normal"][0], dtype=np.float32)
    mask = np.asarray(raw_output["mask"][0], dtype=np.float32)
    metric_scale = np.float32(np.asarray(raw_output["metric_scale"]).reshape(-1)[0])
    height, width = mask.shape
    aspect_ratio = width / height
    if fov_x is None:
        focal, shift = recover_focal_shift(points, mask > 0.5)
        diagonal_factor = (1.0 + aspect_ratio**2) ** 0.5
        fx = focal / 2.0 * diagonal_factor / aspect_ratio
        fy = focal / 2.0 * diagonal_factor
    else:
        if not 0.0 < fov_x < 180.0:
            raise ValueError("Horizontal FOV must be between 0 and 180 degrees")
        fx = 0.5 / np.tan(np.deg2rad(fov_x) / 2)
        fy = fx * aspect_ratio
        if source_valid is not None:
            mask = mask * np.asarray(source_valid, dtype=bool)
        shift, valid = recover_known_fov_shift(points, mask, fx, fy)
        mask = np.where(valid, mask, 0.0)
    intrinsics = np.array(
        ((fx, 0.0, 0.5), (0.0, fy, 0.5), (0.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    depth = points[..., 2] + shift
    depth = depth * metric_scale
    if fov_x is not None:
        valid = np.isfinite(depth) & (depth > 0)
        mask = np.where(valid, mask, 0.0)
        depth = np.where(valid, depth, 1.0)
    points = depth_to_points(depth, intrinsics)
    return {
        "points": points.astype(np.float32),
        "depth": depth.astype(np.float32),
        "normal": normal,
        "mask": mask,
        "intrinsics": intrinsics,
    }


def infer(session, image, resolution_level, *, release_memory=True,
          fov_x=None, source_valid=None):
    import numpy as np

    level = min(max(int(resolution_level), 0), 9)
    num_tokens = int(MIN_TOKENS + level / 9.0 * (MAX_TOKENS - MIN_TOKENS))
    image_input = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32)
    input_feed = {
        "image": image_input,
        "num_tokens": np.asarray(num_tokens, dtype=np.int64),
    }
    output_names = {output.name for output in session.get_outputs()}
    scale_name = "metric_scale" if "metric_scale" in output_names else "scale"
    names = ("points", "normal", "mask", scale_name)
    values = run_session(
        session,
        list(names),
        input_feed,
        release_memory=release_memory,
    )
    raw_output = dict(zip(names, values))
    raw_output["metric_scale"] = raw_output.pop(scale_name)
    return postprocess(raw_output, fov_x=fov_x, source_valid=source_valid)
