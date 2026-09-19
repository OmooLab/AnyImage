"""Build the planar and relief geometry used by the Cutout mainline."""

import math
from dataclasses import dataclass

from ...preferences import addon_preferences, configured_min_cutout_relative_edge_length
from ...common.image import image_empty_bounds
from . import balloon


@dataclass(frozen=True)
class SelectionContours:
    components: tuple
    image_size: tuple[int, int]

    def __post_init__(self):
        components = tuple(
            tuple(
                tuple((float(x), float(y)) for x, y in contour) for contour in component
            )
            for component in self.components
        )
        image_size = tuple(int(value) for value in self.image_size)
        if not components or any(not component for component in components):
            raise ValueError("The Selection has no usable outline components")
        if any(len(contour) < 3 for component in components for contour in component):
            raise ValueError("A Selection outline has fewer than three points")
        if len(image_size) != 2 or min(image_size) <= 0:
            raise ValueError("The Selection outline image size is invalid")
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "image_size", image_size)


def _choose_boundary_edge(start, direction, candidates):
    right = (-direction[1], direction[0])
    left = (direction[1], -direction[0])
    back = (-direction[0], -direction[1])
    preference = {right: 0, direction: 1, left: 2, back: 3}
    return min(
        candidates,
        key=lambda end: preference.get(
            (end[0] - start[0], end[1] - start[1]),
            4,
        ),
    )


def _simplify_axis_aligned_contour(points):
    simplified = []
    for index, current in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        first = (current[0] - previous[0], current[1] - previous[1])
        second = (following[0] - current[0], following[1] - current[1])
        if first[0] * second[1] - first[1] * second[0] != 0:
            simplified.append(current)
    return simplified


def _trace_selection_contours(mask):
    import numpy as np

    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("Cutout Alpha must be two-dimensional")
    height, width = mask.shape
    edges = {}

    def add_edge(start, end):
        edges.setdefault(start, []).append(end)

    top = mask.copy()
    top[1:] &= ~mask[:-1]
    for y, x in np.argwhere(top):
        add_edge((int(x), int(y)), (int(x) + 1, int(y)))

    right = mask.copy()
    right[:, :-1] &= ~mask[:, 1:]
    for y, x in np.argwhere(right):
        add_edge((int(x) + 1, int(y)), (int(x) + 1, int(y) + 1))

    bottom = mask.copy()
    bottom[:-1] &= ~mask[1:]
    for y, x in np.argwhere(bottom):
        add_edge((int(x) + 1, int(y) + 1), (int(x), int(y) + 1))

    left = mask.copy()
    left[:, 1:] &= ~mask[:, :-1]
    for y, x in np.argwhere(left):
        add_edge((int(x), int(y) + 1), (int(x), int(y)))
    if not edges:
        raise ValueError("The Cutout selection has no usable boundary")

    contours = []
    edge_count = sum(len(values) for values in edges.values())
    while edges:
        start = min(edges, key=lambda point: (point[1], point[0]))
        current = start
        direction = (1, 0)
        contour = []
        for _index in range(edge_count + 1):
            contour.append(current)
            candidates = edges.get(current)
            if not candidates:
                raise ValueError("The Cutout boundary is open")
            following = _choose_boundary_edge(current, direction, candidates)
            candidates.remove(following)
            if not candidates:
                del edges[current]
            direction = (following[0] - current[0], following[1] - current[1])
            current = following
            if current == start:
                break
        else:
            raise ValueError("The Cutout boundary could not be closed")
        contour = _simplify_axis_aligned_contour(contour)
        if len(contour) >= 3:
            contours.append(contour)
    if not contours:
        raise ValueError("The Cutout selection is too small")
    return contours


def _signed_contour_area(contour):
    return 0.5 * sum(
        start[0] * end[1] - end[0] * start[1]
        for start, end in zip(contour, contour[1:] + contour[:1])
    )


def _point_inside_contour(point, contour):
    inside = False
    previous = contour[-1]
    for current in contour:
        if (current[1] > point[1]) != (previous[1] > point[1]):
            crossing_x = current[0] + (
                (point[1] - current[1])
                * (previous[0] - current[0])
                / (previous[1] - current[1])
            )
            inside ^= point[0] < crossing_x
        previous = current
    return inside


def _group_selection_contours(mask):
    contours = _trace_selection_contours(mask)
    outer = [contour for contour in contours if _signed_contour_area(contour) > 0.0]
    holes = [contour for contour in contours if _signed_contour_area(contour) < 0.0]
    if not outer:
        raise ValueError("The Cutout selection has no outer boundary")
    components = [[contour] for contour in outer]
    outer_areas = [abs(_signed_contour_area(contour)) for contour in outer]
    for hole in holes:
        start = hole[0]
        end = hole[1]
        edge_x = end[0] - start[0]
        edge_y = end[1] - start[1]
        length = max((edge_x * edge_x + edge_y * edge_y) ** 0.5, 1e-12)
        sample = (
            (start[0] + end[0]) * 0.5 - edge_y * 0.25 / length,
            (start[1] + end[1]) * 0.5 + edge_x * 0.25 / length,
        )
        owners = [
            index
            for index, contour in enumerate(outer)
            if _point_inside_contour(sample, contour)
        ]
        if not owners:
            raise ValueError("The Cutout hole has no enclosing selection component")
        owner = min(owners, key=outer_areas.__getitem__)
        components[owner].append(hole)
    return components


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


def extract_selection_contours(selection_values, max_resolution=512, threshold=0.5):
    import numpy as np

    values = np.asarray(selection_values)
    if values.ndim != 2:
        raise ValueError("Cutout Alpha must be two-dimensional")
    if np.issubdtype(values.dtype, np.floating):
        values = np.clip(values, 0.0, 1.0) * 255.0
    else:
        values = np.clip(values, 0, 255).astype(np.float32)
    source_size = (values.shape[1], values.shape[0])
    scale = min(1.0, float(max_resolution) / max(source_size))
    sampled_size = tuple(max(1, round(value * scale)) for value in source_size)
    if sampled_size != source_size:
        values = _resize_values(values, sampled_size)
    mask = (values > 0.0) & (values >= 255.0 * threshold)
    components = _group_selection_contours(mask)
    scale_x = source_size[0] / sampled_size[0]
    scale_y = source_size[1] / sampled_size[1]
    return SelectionContours(
        components=tuple(
            tuple(
                tuple(
                    (
                        min(max(float(x) * scale_x, 0.0), source_size[0]),
                        min(max(float(y) * scale_y, 0.0), source_size[1]),
                    )
                    for x, y in contour
                )
                for contour in component
            )
            for component in components
        ),
        image_size=source_size,
    )

def contour_area(points):
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    following = np.roll(points, -1, axis=0)
    return 0.5 * float(
        np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1])
    )


def resample_closed_contour(contour, spacing):
    import numpy as np

    points = np.asarray(contour, dtype=np.float64)
    if len(points) < 3:
        raise ValueError("The lasso does not define a valid image selection")
    segments = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(segments, axis=1)
    points = points[lengths > 1e-8]
    if len(points) < 3:
        raise ValueError("The selection is too small to create a Cutout")
    segments = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(segments, axis=1)
    perimeter = float(lengths.sum())
    if perimeter <= spacing * 3.0:
        raise ValueError("The selection is too small to create a Cutout")
    count = max(3, int(round(perimeter / spacing)))
    distances = np.arange(count, dtype=np.float64) * perimeter / count
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    indices = np.searchsorted(cumulative[1:], distances, side="right")
    factors = (distances - cumulative[indices]) / lengths[indices]
    return points[indices] + segments[indices] * factors[:, None]


def smooth_selection_contour(contour, spacing, iterations=16):
    contour = resample_closed_contour(contour, spacing * 0.25)
    original_area = abs(contour_area(contour))
    for _index in range(iterations):
        import numpy as np

        contour = (
            np.roll(contour, 1, axis=0) * 0.125
            + contour * 0.75
            + np.roll(contour, -1, axis=0) * 0.125
        )
    smooth_area = abs(contour_area(contour))
    if original_area > 0.0 and smooth_area > 0.0:
        center = contour.mean(axis=0)
        contour = center + (contour - center) * math.sqrt(original_area / smooth_area)
    contour = resample_closed_contour(contour, spacing)
    if contour_area(contour) < 0.0:
        contour = contour[::-1].copy()
    return contour


def _contour_edges(contours):
    import numpy as np

    starts = []
    ends = []
    for contour in contours:
        contour = np.asarray(contour, dtype=np.float64)
        following = np.roll(contour, -1, axis=0)
        usable = np.abs(following[:, 1] - contour[:, 1]) > 1e-12
        starts.append(contour[usable])
        ends.append(following[usable])
    if not starts:
        empty = np.empty((0, 2), dtype=np.float64)
        return empty, empty
    return np.concatenate(starts), np.concatenate(ends)


def _edge_bucket_indices(starts, ends, minimum_y, bucket_height, bucket_count):
    import numpy as np

    lower = np.minimum(starts[:, 1], ends[:, 1])
    upper = np.maximum(starts[:, 1], ends[:, 1])
    first = np.floor((lower - minimum_y) / bucket_height).astype(np.int64)
    last = np.floor((np.nextafter(upper, lower) - minimum_y) / bucket_height).astype(
        np.int64
    )
    first = np.clip(first, 0, bucket_count - 1)
    last = np.clip(last, 0, bucket_count - 1)
    buckets = [[] for _index in range(bucket_count)]
    for edge_index, (start, stop) in enumerate(zip(first, last)):
        for bucket_index in range(int(start), int(stop) + 1):
            buckets[bucket_index].append(edge_index)
    return buckets


def points_inside_contours(points, contours):
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    inside = np.zeros(len(points), dtype=bool)
    if not len(points):
        return inside
    starts, ends = _contour_edges(contours)
    if not len(starts):
        return inside
    minimum_y = min(float(points[:, 1].min()), float(starts[:, 1].min()))
    maximum_y = max(float(points[:, 1].max()), float(starts[:, 1].max()))
    typical_span = float(np.median(np.abs(ends[:, 1] - starts[:, 1])))
    bucket_height = max(typical_span, (maximum_y - minimum_y) / 4096.0, 1e-9)
    bucket_count = max(1, int(math.ceil((maximum_y - minimum_y) / bucket_height)))
    edge_buckets = _edge_bucket_indices(
        starts, ends, minimum_y, bucket_height, bucket_count
    )
    point_buckets = np.floor((points[:, 1] - minimum_y) / bucket_height).astype(
        np.int64
    )
    point_buckets = np.clip(point_buckets, 0, bucket_count - 1)
    order = np.argsort(point_buckets, kind="stable")
    ordered_buckets = point_buckets[order]
    split = np.flatnonzero(np.diff(ordered_buckets)) + 1
    for indices in np.split(order, split):
        edge_indices = edge_buckets[int(point_buckets[indices[0]])]
        if not edge_indices:
            continue
        selected_starts = starts[edge_indices]
        selected_ends = ends[edge_indices]
        sample_y = points[indices, 1, None]
        crosses = (selected_starts[None, :, 1] > sample_y) != (
            selected_ends[None, :, 1] > sample_y
        )
        crossing_x = selected_starts[None, :, 0] + (
            (sample_y - selected_starts[None, :, 1])
            * (selected_ends[None, :, 0] - selected_starts[None, :, 0])
            / (selected_ends[None, :, 1] - selected_starts[None, :, 1])
        )
        inside[indices] = (
            np.count_nonzero(crosses & (points[indices, 0, None] < crossing_x), axis=1)
            % 2
            == 1
        )
    return inside


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


def contour_interior_point(contours, spacing):
    """Choose an interior seed from the largest auxiliary triangle."""
    import numpy as np
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt

    input_points = np.concatenate(contours, axis=0)
    boundary_edges = []
    offset = 0
    for contour in contours:
        count = len(contour)
        boundary_edges.extend(
            (offset + index, offset + (index + 1) % count) for index in range(count)
        )
        offset += count
    result = delaunay_2d_cdt(
        [Vector(point) for point in input_points],
        boundary_edges,
        [],
        0,
        max(spacing * 1e-6, 1e-9),
        False,
    )
    planar_points = np.asarray(
        [tuple(point) for point in result[0]],
        dtype=np.float64,
    )
    faces = np.asarray(
        [tuple(face) for face in result[2] if len(face) == 3],
        dtype=np.int32,
    )
    if len(faces):
        centers = planar_points[faces].mean(axis=1)
        faces = faces[points_inside_contours(centers, contours)]
    if not len(faces):
        raise ValueError("Unable to triangulate the Cutout selection components")
    triangles = planar_points[faces]
    first = triangles[:, 1] - triangles[:, 0]
    second = triangles[:, 2] - triangles[:, 0]
    areas = abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0])
    seed = triangles[np.argmax(areas)].mean(axis=0)
    if not points_inside_contours(seed[None], contours)[0]:
        raise ValueError("Cutout seed is outside its contour")
    return seed



def boundary_vertices_from_faces(vertex_count, faces):
    import numpy as np

    faces = np.asarray(faces, dtype=np.int32)
    boundary = np.zeros(vertex_count, dtype=bool)
    if not len(faces):
        return boundary
    edges = np.concatenate(
        [
            faces[:, (index, (index + 1) % faces.shape[1])]
            for index in range(faces.shape[1])
        ],
        axis=0,
    )
    edges.sort(axis=1)
    unique_edges, users = np.unique(edges, axis=0, return_counts=True)
    boundary[unique_edges[users == 1].ravel()] = True
    return boundary


CUTOUT_ALPHA_THRESHOLD = 0.9


@dataclass(frozen=True)
class BaseShape:
    vertices: object
    faces: object
    uv: object
    balloon: object
    mask: object


def cutout_domain(mesh, bounds, world_metric, balloon_algorithm="POISSON"):
    """Map the quality mesh into local coordinates and solve its height."""
    import numpy as np

    x_min, x_max, y_min, y_max = bounds
    pixels, planar_faces, boundary, pixel_components, image_size = mesh
    image_width, image_height = image_size
    transform = metric_transform(world_metric)

    def pixel_to_planar(points):
        local = np.asarray(points, dtype=np.float64).copy()
        local[:, 0] = x_min + local[:, 0] * (x_max - x_min) / image_width
        local[:, 1] = y_max - local[:, 1] * (y_max - y_min) / image_height
        return local @ transform

    planar = pixel_to_planar(pixels)
    components = [
        (start, end, faces.tolist(), pixel_to_planar(contour))
        for start, end, faces, contour in pixel_components
    ]
    profile = balloon.balloon_profile(
        balloon_algorithm, planar, planar_faces, boundary, components
    )
    faces = np.asarray(planar_faces, dtype=np.int32)
    local = planar @ np.linalg.inv(metric_transform(world_metric))
    uv = np.column_stack(
        (
            (local[:, 0] - x_min) / (x_max - x_min),
            (local[:, 1] - y_min) / (y_max - y_min),
        )
    ).astype(np.float32)
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
    return vertices, faces, uv, boundary, planar, profile


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
    source_object,
    edge_length,
    content_values,
    content_bounds,
    threshold=CUTOUT_ALPHA_THRESHOLD,
):
    """Resolve target spacing in Blender world units from visible content bounds."""
    import numpy as np

    if not math.isfinite(edge_length) or edge_length <= 0:
        raise ValueError("Cutout edge length must be greater than zero")
    values = np.asarray(content_values)
    visible = (values > 0) & (values >= threshold)
    rows = np.flatnonzero(visible.any(axis=1))
    columns = np.flatnonzero(visible.any(axis=0))
    if not len(rows):
        raise ValueError("The Cutout selection contains no visible image pixels")
    bounds = crop_plane_bounds(
        source_object, content_bounds, tuple(source_object.data.size)
    )
    metric, _ = world_plane_metric(source_object.matrix_world)
    metric_transform(metric)
    width = (
        (bounds[1] - bounds[0]) * (columns.max() + 1 - columns.min()) / values.shape[1]
    )
    height = (bounds[3] - bounds[2]) * (rows.max() + 1 - rows.min()) / values.shape[0]
    longest = max(width * math.sqrt(metric[0][0]), height * math.sqrt(metric[1][1]))
    return max(
        float(edge_length),
        longest * configured_min_cutout_relative_edge_length(context),
    )


def build_reference_mask(content_values, image_size):
    """Resample Cutout content into a boolean mask at Depth texture resolution."""
    import numpy as np

    values = np.asarray(content_values, dtype=np.float32)
    target_width, target_height = (int(value) for value in image_size)
    return _resize_values(values, (target_width, target_height)) > 0.5


def build_base_shape(
    context,
    source_object,
    edge_length,
    content_values,
    content_bounds,
    *,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    fine_outline=False,
):
    import numpy as np

    bounds = crop_plane_bounds(
        source_object,
        content_bounds,
        tuple(source_object.data.size),
    )
    world_metric, world_z_scale = world_plane_metric(source_object.matrix_world)
    if world_z_scale <= 1e-10:
        raise ValueError("The Image Empty has a degenerate world transform")
    pixel_transform = np.diag(
        (
            (bounds[1] - bounds[0]) / content_values.shape[1],
            -(bounds[3] - bounds[2]) / content_values.shape[0],
        )
    ) @ metric_transform(world_metric)
    from .mesh import build_mesh

    mesh_result = build_mesh(
        content_values,
        edge_length,
        alpha_threshold,
        pixel_transform=pixel_transform,
        fine_outline=fine_outline,
    )
    *mesh_geometry, mask = mesh_result
    mesh = (
        *mesh_geometry,
        (content_values.shape[1], content_values.shape[0]),
    )
    preferences = addon_preferences(context)
    balloon_algorithm = getattr(preferences, "balloon_profile_algorithm", "POISSON")
    domain = cutout_domain(mesh, bounds, world_metric, balloon_algorithm)
    source_vertices, faces, uv, _boundary, planar, balloon = domain
    return BaseShape(
        vertices=np.asarray(source_vertices, dtype=np.float64),
        faces=counter_clockwise_faces(planar, faces),
        uv=np.asarray(uv, dtype=np.float32),
        balloon=np.asarray(balloon, dtype=np.float64) / world_z_scale,
        mask=np.asarray(mask, dtype=bool),
    )
