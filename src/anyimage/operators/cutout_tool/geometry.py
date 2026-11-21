"""Build the planar and relief geometry used by the Cutout mainline."""

import math
from dataclasses import dataclass

import bpy

from ...preferences import addon_preferences, configured_min_cutout_relative_edge_length
from ...common.image import image_empty_bounds
from ...common.selection import ImageEditWarning, visible_pixel_bounds
from . import balloon
from .mesh import build_mesh


def _resize_values(values, size):
    import numpy as np

    target_width, target_height = (int(value) for value in size)
    source_height, source_width = values.shape
    if (target_width, target_height) == (source_width, source_height):
        return values
    x = (np.arange(target_width, dtype=np.float32) + 0.5) * (
        source_width / target_width
    ) - 0.5
    y = (np.arange(target_height, dtype=np.float32) + 0.5) * (
        source_height / target_height
    ) - 0.5
    x0_unclipped = np.floor(x).astype(np.int32)
    y0_unclipped = np.floor(y).astype(np.int32)
    x_weight = x - x0_unclipped
    y_weight = y - y0_unclipped
    x0 = np.clip(x0_unclipped, 0, source_width - 1)
    y0 = np.clip(y0_unclipped, 0, source_height - 1)
    x1 = np.clip(x0_unclipped + 1, 0, source_width - 1)
    y1 = np.clip(y0_unclipped + 1, 0, source_height - 1)
    horizontal = (
        values[:, x0] * (1.0 - x_weight)[None, :] + values[:, x1] * x_weight[None, :]
    )
    return (
        horizontal[y0] * (1.0 - y_weight)[:, None] + horizontal[y1] * y_weight[:, None]
    )


def metric_transform(world_metric=None):
    import numpy as np

    metric = (
        np.eye(2, dtype=np.float64)
        if world_metric is None
        else np.asarray(world_metric, dtype=np.float64)
    )
    if metric.shape != (2, 2):
        raise ValueError("The Image Empty has an invalid world transform")
    try:
        return np.linalg.cholesky(metric)
    except np.linalg.LinAlgError as error:
        raise ValueError("The Image Empty has a degenerate world transform") from error


CUTOUT_ALPHA_THRESHOLD = 0.9


@dataclass(frozen=True)
class BaseShape:
    vertices: object
    faces: object
    uv: object
    balloon: object
    mask: object


def cutout_domain(mesh, bounds, transform, balloon_algorithm="POISSON"):
    """Map the quality mesh into local coordinates and solve its height."""
    import numpy as np

    x_min, x_max, y_min, y_max = bounds
    pixels, planar_faces, boundary, pixel_components, mask = mesh
    image_height, image_width = mask.shape

    def pixel_to_local(points):
        local = np.asarray(points, dtype=np.float64).copy()
        local[:, 0] = x_min + local[:, 0] * (x_max - x_min) / image_width
        local[:, 1] = y_max - local[:, 1] * (y_max - y_min) / image_height
        return local

    local = pixel_to_local(pixels)
    planar = local @ transform
    # Only Teddy consumes individual component faces and contours.
    components = (
        (start, end, faces.tolist(), pixel_to_local(contour) @ transform)
        for start, end, faces, contour in pixel_components
    )
    profile = balloon.balloon_profile(
        balloon_algorithm, planar, planar_faces, boundary, components
    )
    faces = counter_clockwise_faces(planar, planar_faces)
    uv = np.column_stack((pixels[:, 0] / image_width, 1.0 - pixels[:, 1] / image_height))
    uv = uv.astype(np.float32)
    crop_center = np.asarray(
        ((x_min + x_max) * 0.5, (y_min + y_max) * 0.5),
        dtype=np.float64,
    )
    local -= crop_center
    vertices = np.column_stack(
        (
            local[:, 0],
            np.zeros(len(local), dtype=np.float64),
            local[:, 1],
        )
    )
    return vertices, faces, uv, profile


def world_plane_metric(matrix_world):
    from mathutils import Vector

    linear = matrix_world.to_3x3()
    x = linear @ Vector((1.0, 0.0, 0.0))
    y = linear @ Vector((0.0, 1.0, 0.0))
    z = linear @ Vector((0.0, 0.0, 1.0))
    return ((x.dot(x), x.dot(y)), (x.dot(y), y.dot(y))), z.length


def counter_clockwise_faces(points, faces):
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    result = np.asarray(faces, dtype=np.int32).copy()
    polygons = points[result]
    following = np.roll(polygons, -1, axis=1)
    signed_area = np.sum(
        polygons[..., 0] * following[..., 1] - polygons[..., 1] * following[..., 0],
        axis=1,
    )
    result[signed_area < 0.0] = result[signed_area < 0.0, ::-1]
    return result


def crop_plane_bounds(source_object, crop_bounds, source_size):
    source_width, source_height = (float(value) for value in source_size)
    left, top, right, bottom = (float(value) for value in crop_bounds)
    x_min, x_max, y_min, y_max = image_empty_bounds(source_object)
    width = x_max - x_min
    height = y_max - y_min
    return (
        x_min + left * width / source_width,
        x_min + right * width / source_width,
        y_max - bottom * height / source_height,
        y_max - top * height / source_height,
    )


def effective_cutout_edge_length(
    context,
    bounds,
    edge_length,
    visible,
    metric,
):
    """Resolve target spacing in Blender world units from visible content bounds."""
    if not math.isfinite(edge_length) or edge_length <= 0:
        raise ValueError("Cutout edge length must be greater than zero")
    visible_bounds = visible_pixel_bounds(visible)
    if visible_bounds is None:
        raise ValueError("The Cutout selection contains no visible image pixels")
    left, top, right, bottom = visible_bounds
    width = (bounds[1] - bounds[0]) * (right - left) / visible.shape[1]
    height = (bounds[3] - bounds[2]) * (bottom - top) / visible.shape[0]
    longest = max(width * math.sqrt(metric[0][0]), height * math.sqrt(metric[1][1]))
    return max(
        float(edge_length),
        longest * configured_min_cutout_relative_edge_length(context),
    )


def visible_cutout_pixels(values, threshold):
    return (values > 0) & (values >= threshold)


def build_reference_mask(content_values, image_size, alpha_threshold):
    """Resample Cutout content into a boolean mask at Depth texture resolution."""
    import numpy as np

    values = np.asarray(content_values, dtype=np.float32)
    values = _resize_values(values, image_size)
    return visible_cutout_pixels(values, alpha_threshold)


def build_cutout_shape(
    context,
    source_object,
    edge_length,
    content_values,
    bounds,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    fine_outline=False,
    report=None,
):
    import numpy as np

    values = np.asarray(content_values)
    if values.ndim != 2 or not values.size or not np.isfinite(values).all():
        raise ValueError("The Cutout Alpha must be a finite two-dimensional array")
    visible = visible_cutout_pixels(values, alpha_threshold)
    world_metric, world_z_scale = world_plane_metric(source_object.matrix_world)
    if world_z_scale <= 1e-10:
        raise ValueError("The Image Empty has a degenerate world transform")
    transform = metric_transform(world_metric)
    pixel_transform = np.diag(
        (
            (bounds[1] - bounds[0]) / visible.shape[1],
            -(bounds[3] - bounds[2]) / visible.shape[0],
        )
    ) @ transform

    effective_length = effective_cutout_edge_length(
        context, bounds, edge_length, visible, world_metric
    )
    if report is not None and effective_length > edge_length * (1 + 1e-6):
        units = context.scene.unit_settings
        label = bpy.utils.units.to_string(
            units.system if units.system != "NONE" else "METRIC",
            "LENGTH",
            effective_length * units.scale_length,
            precision=4,
        )
        report(
            {"INFO"},
            bpy.app.translations.pgettext_rpt("Effective Edge Length: {length}").format(
                length=label
            ),
        )
    preferences = addon_preferences(context)
    balloon_algorithm = getattr(preferences, "balloon_profile_algorithm", "POISSON")
    mesh = build_mesh(
        visible,
        effective_length,
        pixel_transform=pixel_transform,
        fine_outline=fine_outline,
        include_components=str(balloon_algorithm).upper() == "TEDDY",
    )
    source_vertices, faces, uv, balloon = cutout_domain(mesh, bounds, transform, balloon_algorithm)
    return BaseShape(
        vertices=np.asarray(source_vertices, dtype=np.float64),
        faces=faces,
        uv=np.asarray(uv, dtype=np.float32),
        balloon=np.asarray(balloon, dtype=np.float64) / world_z_scale,
        mask=mesh[-1],
    )


def cutout_content_values(
    source_alpha, selection_values=None, *, alpha_threshold=CUTOUT_ALPHA_THRESHOLD
):
    """Combine local image Alpha with optional pure Selection geometry."""
    import numpy as np

    alpha = np.asarray(source_alpha, dtype=np.float32)
    if alpha.ndim != 2:
        raise ValueError("The Cutout source Alpha must be two-dimensional")
    if selection_values is None:
        values = alpha.copy()
    else:
        selection = np.asarray(selection_values, dtype=np.float32)
        if alpha.shape != selection.shape:
            raise ValueError("The Cutout source Alpha does not match the Selection")
        values = alpha * selection
    if not np.any(visible_cutout_pixels(values, alpha_threshold)):
        raise ImageEditWarning("The Cutout selection contains no visible image pixels")
    return values
