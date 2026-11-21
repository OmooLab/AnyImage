"""Extract, smooth, and validate Cutout boundary contours."""

import math

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .polygon import approximate_polygon


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
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 2:
        raise ValueError("Cutout Alpha must be two-dimensional")
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


def extract_selection_contours(mask):
    """Group pixel-boundary rings of a binary mask by their enclosing outline."""
    components = []
    outer_areas = []
    holes = []
    for contour in _trace_selection_contours(mask):
        area = contour_area(contour)
        if area > 0:
            components.append([contour])
            outer_areas.append(area)
        elif area < 0:
            holes.append(contour)
    if not components:
        raise ValueError("The Cutout selection has no outer boundary")
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
            for index, component in enumerate(components)
            if _point_inside_contour(sample, component[0])
        ]
        if not owners:
            raise ValueError("The Cutout hole has no enclosing selection component")
        owner = min(owners, key=outer_areas.__getitem__)
        components[owner].append(hole)
    return components


def contour_area(points):
    points = np.asarray(points, dtype=np.float64)
    following = np.roll(points, -1, axis=0)
    return 0.5 * float(
        np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1])
    )


def resample_closed_contour(contour, spacing):
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


def _crossing_edges(contours):
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
    points = np.asarray(points, dtype=np.float64)
    inside = np.zeros(len(points), dtype=bool)
    if not len(points):
        return inside
    starts, ends = _crossing_edges(contours)
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


def contour_edge_indices(contours):
    """Index the closed edges of each ring in their concatenated vertex array."""
    edges = []
    offset = 0
    for contour in contours:
        count = len(contour)
        edges.extend((offset + i, offset + (i + 1) % count) for i in range(count))
        offset += count
    return edges


def contour_interior_point(contours, spacing):
    """Choose an interior seed from the largest auxiliary triangle."""
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt

    input_points = np.concatenate(contours, axis=0)
    result = delaunay_2d_cdt(
        [Vector(point) for point in input_points],
        contour_edge_indices(contours),
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
    triangles = planar_points[faces.reshape(-1, 3)]
    centers = triangles.mean(axis=1)
    inside = np.flatnonzero(points_inside_contours(centers, contours))
    if not len(inside):
        raise ValueError("Unable to triangulate the Cutout selection components")
    triangles = triangles[inside]
    first = triangles[:, 1] - triangles[:, 0]
    second = triangles[:, 2] - triangles[:, 0]
    areas = abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0])
    return centers[inside[np.argmax(areas)]]



def separate_contour_contacts(contours):
    """Open pixel-corner contacts with a subpixel bevel in each incident ring."""
    points = np.concatenate(contours)
    pairs = cKDTree(points).query_pairs(1e-8)
    if not pairs:
        return contours
    contacts = {i for pair in pairs for i in pair}
    result = []
    offset = 0
    for contour in contours:
        ring = contour.copy()
        for i in range(len(ring)):
            if offset + i in contacts:
                before = contour[i-1] - contour[i]
                after = contour[(i+1) % len(ring)] - contour[i]
                length = min(np.linalg.norm(before), np.linalg.norm(after))
                direction = (
                    before / np.linalg.norm(before) + after / np.linalg.norm(after)
                )
                ring[i] += direction * length * 0.125
        result.append(ring)
        offset += len(ring)
    return result


def valid_contours(contours):
    """Reject crossing rings and holes moved outside the outer ring."""
    starts = np.concatenate(contours)
    if cKDTree(starts).query_pairs(1e-8):
        return False
    ends = np.concatenate([np.roll(c, -1, axis=0) for c in contours])
    delta = ends - starts
    count = len(starts)
    following = np.concatenate(
        [
            np.roll(np.arange(len(contour)) + sum(map(len, contours[:index])), -1)
            for index, contour in enumerate(contours)
        ]
    )
    for first in range(0, count, 32):
        ids = np.arange(first, min(first + 32, count))[:, None]
        other = np.arange(count)[None, :]
        a = starts[first : first + 32, None]
        v = delta[first : first + 32, None]
        w = delta[None]
        d = starts[None] - a
        determinant = v[..., 0] * w[..., 1] - v[..., 1] * w[..., 0]
        divisor = np.where(np.abs(determinant) > 1e-12, determinant, 1.0)
        t = (d[..., 0] * w[..., 1] - d[..., 1] * w[..., 0]) / divisor
        u = (d[..., 0] * v[..., 1] - d[..., 1] * v[..., 0]) / divisor
        adjacent = (other == following[ids]) | (ids == following[other])
        if np.any(
            (other > ids)
            & ~adjacent
            & (np.abs(determinant) > 1e-12)
            & (t >= -1e-9)
            & (t <= 1 + 1e-9)
            & (u >= -1e-9)
            & (u <= 1 + 1e-9)
        ):
            return False
    return all(
        points_inside_contours(hole[:1], contours[:1])[0] for hole in contours[1:]
    )


def contours_for_component(component, spacing, strength=1.0, *, pixel_transform=None):
    """Soften pixel steps before simplifying in the target edge-length metric."""
    result = []
    transform = np.eye(2) if pixel_transform is None else pixel_transform
    inverse = np.linalg.inv(transform)
    tolerance = spacing * 0.078125
    for contour in component:
        original = np.asarray(contour, dtype=float)
        if strength > 0:
            original = ndimage.gaussian_filter1d(
                resample_closed_contour(original @ inverse, 0.5),
                1.6 * strength,
                axis=0,
                mode="wrap",
            ) @ transform
        for error in (tolerance * strength, tolerance * strength * 0.5, 0):
            simplified = approximate_polygon(np.vstack((original, original[0])), error)[
                :-1
            ]
            if len(simplified) >= 3 and abs(contour_area(simplified)) > 0.05:
                break
        points = []
        for a, b in zip(simplified, np.roll(simplified, -1, axis=0)):
            count = max(1, int(np.ceil(np.linalg.norm(b - a) / spacing)))
            points.extend(a + np.arange(count)[:, None] / count * (b - a))
        result.append(np.asarray(points))
    if not valid_contours(result):
        if strength == 0:
            raise ValueError("Cutout outline is invalid")
        return contours_for_component(
            component, spacing, strength * 0.5 if strength > 0.125 else 0,
            pixel_transform=transform,
        )
    return result
