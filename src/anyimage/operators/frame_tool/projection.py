"""Project image planes and place the view-facing Frame result."""

import math
from ...common.image import MAX_PROJECTIVE_OUTPUT_PIXELS
from ...common.selection import clip_polygon_halfplanes


PROJECTIVE_RELATIVE_EPSILON = 1e-12


def _matrix_array(matrix):
    import numpy as np

    return np.asarray(
        tuple(tuple(float(value) for value in row) for row in matrix),
        dtype=np.float64,
    )


def frame_source_projection(
    projection_matrix,
    view_matrix,
    matrix_world,
    bounds,
    region_size,
    *,
    perspective,
):
    """Return normalized image-plane transforms for one frozen view."""
    import numpy as np

    x_min, x_max, y_min, y_max = (float(value) for value in bounds)
    region_width, region_height = (float(value) for value in region_size)
    if min(x_max - x_min, y_max - y_min, region_width, region_height) <= 0.0:
        raise ValueError("The Image Empty projection is invalid")
    source_plane = np.asarray(
        (
            (x_max - x_min, 0.0, x_min),
            (0.0, y_min - y_max, y_max),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    world = _matrix_array(matrix_world)
    source_to_world = world @ source_plane
    source_to_view = _matrix_array(view_matrix) @ source_to_world
    source_to_clip = _matrix_array(projection_matrix) @ source_to_world
    source_to_screen = np.stack(
        (
            0.5 * (source_to_clip[0] + source_to_clip[3]),
            0.5 * (source_to_clip[1] + source_to_clip[3]),
            source_to_clip[3],
        )
    )
    scale = float(np.max(np.abs(source_to_screen)))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("The Image Empty projection is invalid")
    source_to_screen /= scale
    if not np.isfinite(source_to_screen).all():
        raise ValueError("The Image Empty projection is invalid")
    condition = float(np.linalg.cond(source_to_screen))
    if not math.isfinite(condition) or condition > 1.0 / np.finfo(np.float64).eps:
        raise ValueError("The Image Empty is edge-on to the current view")
    return {
        "bounds": (x_min, x_max, y_min, y_max),
        "origin_depth": -float((_matrix_array(view_matrix) @ world)[2, 3]),
        "perspective": bool(perspective),
        "region_size": (region_width, region_height),
        "screen_to_source": np.linalg.inv(source_to_screen),
        "source_to_screen": source_to_screen,
        "source_to_view": source_to_view,
        "source_to_world": source_to_world,
    }


def _projective_points(points, matrix):
    """Map points and return finite results plus per-point validity."""
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    flat = points.reshape((-1, 2))
    homogeneous = np.column_stack((flat, np.ones(len(flat), dtype=np.float64)))
    mapped = homogeneous @ np.asarray(matrix, dtype=np.float64).T
    magnitude = np.max(np.abs(mapped), axis=1)
    valid = (
        np.isfinite(mapped).all(axis=1)
        & (np.abs(mapped[:, 2]) > PROJECTIVE_RELATIVE_EPSILON * magnitude)
    )
    result = np.full((len(flat), 2), np.nan, dtype=np.float64)
    result[valid] = mapped[valid, :2] / mapped[valid, 2, None]
    return result.reshape(points.shape), valid.reshape(points.shape[:-1])


def frame_source_coordinates(source, screen_points):
    """Return source pixels, view depth, validity, and normalized coordinates."""
    import numpy as np

    screen_points = np.asarray(screen_points, dtype=np.float64)
    region_width, region_height = source["region_size"]
    normalized_screen = screen_points / (region_width, region_height)
    normalized_source, valid = _projective_points(
        normalized_screen,
        source["screen_to_source"],
    )
    flat_source = normalized_source.reshape((-1, 2))
    homogeneous = np.column_stack(
        (flat_source, np.ones(len(flat_source), dtype=np.float64))
    )
    depth = -(homogeneous @ source["source_to_view"][2])
    depth = depth.reshape(valid.shape)
    valid &= np.isfinite(depth)
    if source["perspective"]:
        valid &= depth > 0.0
    valid &= (
        (normalized_source[..., 0] >= 0.0)
        & (normalized_source[..., 0] <= 1.0)
        & (normalized_source[..., 1] >= 0.0)
        & (normalized_source[..., 1] <= 1.0)
    )
    image_width, image_height = source["image_size"]
    source_points = normalized_source * (image_width, image_height)
    source_points[~valid] = -1.0
    return source_points, depth, valid, normalized_source


def frame_source_overlap(source, frame_quad):
    """Clip the source plane before dividing its homogeneous projection."""
    import numpy as np

    frame = np.asarray(frame_quad, dtype=np.float64) / source["region_size"]
    left, bottom = frame.min(axis=0)
    right, top = frame.max(axis=0)
    x, y, w = source["source_to_screen"]
    boundaries = [x - left * w, right * w - x, y - bottom * w, top * w - y]
    if source["perspective"]:
        boundaries.insert(0, -source["source_to_view"][2])
    polygon = clip_polygon_halfplanes(
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), boundaries
    )
    if len(polygon) < 3:
        return ()
    screen, valid = _projective_points(polygon, source["source_to_screen"])
    if not np.all(valid):
        return ()
    screen *= source["region_size"]
    # Center the coordinates to avoid cancellation in a distant small polygon.
    centered = screen - screen[0]
    area = abs(np.sum(centered[:, 0] * np.roll(centered[:, 1], -1)
                      - centered[:, 1] * np.roll(centered[:, 0], -1))) * 0.5
    return tuple(map(tuple, screen)) if area > 1e-8 else ()


def polygon_centroid(polygon):
    """Return the area centroid of one non-degenerate screen polygon."""
    cross_sum = 0.0
    x_sum = 0.0
    y_sum = 0.0
    for first, second in zip(polygon, (*polygon[1:], polygon[0])):
        cross = first[0] * second[1] - second[0] * first[1]
        cross_sum += cross
        x_sum += (first[0] + second[0]) * cross
        y_sum += (first[1] + second[1]) * cross
    if abs(cross_sum) <= 1e-12:
        raise ValueError("Frame does not overlap the active Image Empty")
    return x_sum / (3.0 * cross_sum), y_sum / (3.0 * cross_sum)


def frame_output_size(frame_quad, region_size, max_resolution):
    """Choose output resolution from Frame pixels within the current Region."""
    frame_width = abs(float(frame_quad[1][0] - frame_quad[0][0]))
    frame_height = abs(float(frame_quad[0][1] - frame_quad[3][1]))
    region_width, region_height = (float(value) for value in region_size)
    maximum = float(max_resolution)
    if min(frame_width, frame_height, region_width, region_height, maximum) <= 0.0:
        raise ValueError("The Frame output dimensions must be positive")
    scale = min(
        1.0,
        region_width / frame_width,
        region_height / frame_height,
        maximum / max(frame_width, frame_height),
        math.sqrt(
            MAX_PROJECTIVE_OUTPUT_PIXELS / max(frame_width * frame_height, 1.0)
        ),
    )
    return (
        max(2, int(round(frame_width * scale))),
        max(2, int(round(frame_height * scale))),
    )


def view_facing_frame_geometry(corners, output_size):
    """Return a world matrix array and display size for frame-plane corners."""
    import numpy as np

    corners = np.asarray(corners, dtype=np.float64)
    if corners.shape != (4, 3) or not np.isfinite(corners).all():
        raise ValueError("The Frame view plane is invalid")
    top_left, top_right, _bottom_right, bottom_left = corners
    right = top_right - top_left
    up = top_left - bottom_left
    width = float(np.linalg.norm(right))
    height = float(np.linalg.norm(up))
    if min(width, height) <= 1e-10:
        raise ValueError("Draw a larger Frame")
    right /= width
    up /= height
    forward = np.cross(right, up)
    forward_length = float(np.linalg.norm(forward))
    if forward_length <= 1e-10:
        raise ValueError("The Frame view plane is invalid")
    forward /= forward_length
    matrix = np.identity(4, dtype=np.float64)
    matrix[:3, 0] = right
    matrix[:3, 1] = up
    matrix[:3, 2] = forward
    matrix[:3, 3] = corners.mean(axis=0)
    display_size = width if output_size[0] >= output_size[1] else height
    return matrix, display_size


def frame_result_transform(frame_quad, source_origin, region, view3d, output_size):
    """Return the view-facing object matrix and Image Empty display size."""
    from mathutils import Matrix
    from bpy_extras import view3d_utils

    corners = tuple(
        tuple(
            float(value)
            for value in view3d_utils.region_2d_to_location_3d(
                region,
                view3d,
                point,
                source_origin,
            )
        )
        for point in frame_quad
    )
    matrix, display_size = view_facing_frame_geometry(corners, output_size)
    return Matrix(tuple(tuple(row) for row in matrix)), display_size


def frame_depth_location(active_source, overlap_polygon):
    """Return the world point whose view depth places the Frame result."""
    import numpy as np

    source_object = active_source["object"]
    if not active_source["perspective"] or active_source["origin_depth"] > 0.0:
        return source_object.matrix_world.translation.copy()
    centroid = np.asarray((polygon_centroid(overlap_polygon),), dtype=np.float64)
    _points, depth, valid, normalized_source = frame_source_coordinates(
        active_source,
        centroid,
    )
    if not bool(valid[0]) or depth[0] <= 0.0:
        raise ValueError("The Frame result depth is invalid")
    source_point = np.asarray(
        (normalized_source[0, 0], normalized_source[0, 1], 1.0),
        dtype=np.float64,
    )
    world = active_source["source_to_world"] @ source_point
    if not np.isfinite(world).all() or abs(world[3]) <= 1e-12:
        raise ValueError("The Frame result depth is invalid")
    return tuple(float(value) for value in world[:3] / world[3])
