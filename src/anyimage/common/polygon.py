"""Screen polygon tessellation, scanline fills, and outlines."""

import math


def dashed_line_segments(vertices, dash_length=4.0, gap_length=4.0, offset=0.0):
    if dash_length <= 0.0 or gap_length < 0.0:
        raise ValueError(
            "Dash length must be positive and gap length cannot be negative"
        )
    pattern_length = dash_length + gap_length
    segments = []
    distance_offset = float(offset)
    for start, end in zip(vertices, vertices[1:]):
        start_x, start_y = (float(value) for value in start)
        end_x, end_y = (float(value) for value in end)
        segment_length = math.hypot(end_x - start_x, end_y - start_y)
        if segment_length <= 0.0:
            continue
        direction_x = (end_x - start_x) / segment_length
        direction_y = (end_y - start_y) / segment_length
        position = 0.0
        while position < segment_length:
            phase = (distance_offset + position) % pattern_length
            if phase < dash_length:
                run_length = min(dash_length - phase, segment_length - position)
                segments.extend(
                    (
                        (
                            start_x + direction_x * position,
                            start_y + direction_y * position,
                        ),
                        (
                            start_x + direction_x * (position + run_length),
                            start_y + direction_y * (position + run_length),
                        ),
                    )
                )
            else:
                run_length = min(pattern_length - phase, segment_length - position)
            position += run_length
        distance_offset += segment_length
    return tuple(segments)


def _signed_area(vertices):
    return (
        sum(
            start[0] * end[1] - end[0] * start[1]
            for start, end in zip(vertices, (*vertices[1:], vertices[0]))
        )
        * 0.5
    )


def _triangle_cross(start, middle, end):
    return (middle[0] - start[0]) * (end[1] - start[1]) - (middle[1] - start[1]) * (
        end[0] - start[0]
    )


def _point_in_triangle(point, start, middle, end, orientation, epsilon):
    return all(
        orientation * cross >= -epsilon
        for cross in (
            _triangle_cross(start, middle, point),
            _triangle_cross(middle, end, point),
            _triangle_cross(end, start, point),
        )
    )


def _triangulated_polygon_vertices_python(vertices):
    vertices = tuple(tuple(float(value) for value in vertex) for vertex in vertices)
    if len(vertices) < 3:
        return ()
    area = _signed_area(vertices)
    if abs(area) <= 1e-8:
        return ()
    orientation = 1.0 if area > 0.0 else -1.0
    remaining = list(range(len(vertices)))
    triangles = []
    epsilon = 1e-8
    while len(remaining) > 3:
        for position, current in enumerate(remaining):
            previous = remaining[position - 1]
            following = remaining[(position + 1) % len(remaining)]
            start = vertices[previous]
            middle = vertices[current]
            end = vertices[following]
            if orientation * _triangle_cross(start, middle, end) <= epsilon:
                continue
            if any(
                _point_in_triangle(
                    vertices[index],
                    start,
                    middle,
                    end,
                    orientation,
                    epsilon,
                )
                for index in remaining
                if index not in {previous, current, following}
            ):
                continue
            triangles.extend((start, middle, end))
            del remaining[position]
            break
        else:
            return ()
    triangles.extend(vertices[index] for index in remaining)
    return tuple(triangles)


def triangulated_polygon_vertices(vertices):
    vertices = tuple(tuple(float(value) for value in vertex) for vertex in vertices)
    try:
        import mathutils

        points = [mathutils.Vector((vertex[0], vertex[1], 0.0)) for vertex in vertices]
        triangles = mathutils.geometry.tessellate_polygon([points])
        return tuple(
            (float(point[0]), float(point[1]))
            for triangle in triangles
            for point in triangle
        )
    except (AttributeError, ImportError, RuntimeError, TypeError, ValueError):
        return _triangulated_polygon_vertices_python(vertices)


def _scanline_intervals(vertices, sample_y):
    edges = tuple(zip(vertices, (*vertices[1:], vertices[0])))
    events = []
    for start, end in edges:
        if (start[1] <= sample_y < end[1]) or (end[1] <= sample_y < start[1]):
            factor = (sample_y - start[1]) / (end[1] - start[1])
            events.append(
                (
                    start[0] + (end[0] - start[0]) * factor,
                    1 if end[1] > start[1] else -1,
                )
            )
    events.sort(key=lambda event: event[0])
    intervals = []
    winding = 0
    interval_start = None
    index = 0
    while index < len(events):
        x = events[index][0]
        delta = 0
        while index < len(events) and abs(events[index][0] - x) <= 1e-8:
            delta += events[index][1]
            index += 1
        was_inside = winding != 0
        winding += delta
        is_inside = winding != 0
        if not was_inside and is_inside:
            interval_start = x
        elif was_inside and not is_inside and interval_start is not None:
            intervals.append((interval_start, x))
            interval_start = None
    return tuple(intervals)


def scanline_fill_bands(vertices, step=2.0):
    vertices = tuple(tuple(float(value) for value in vertex) for vertex in vertices)
    if len(vertices) < 3:
        return ()
    minimum_y = min(vertex[1] for vertex in vertices)
    maximum_y = max(vertex[1] for vertex in vertices)
    band_bottom = minimum_y
    bands = []
    while band_bottom < maximum_y:
        band_top = min(band_bottom + step, maximum_y)
        sample_y = (band_bottom + band_top) * 0.5
        intervals = _scanline_intervals(vertices, sample_y)
        bands.append((band_bottom, band_top, tuple(intervals)))
        band_bottom = band_top
    return tuple(bands)


def merge_intervals(intervals):
    merged = []
    for left, right in sorted(intervals):
        if right - left <= 1e-8:
            continue
        if not merged or left > merged[-1][1] + 1e-8:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    return tuple((left, right) for left, right in merged)


def scanline_union_bands(polygons, step=2.0):
    """Union simple polygons into local screen-space scanline bands."""
    polygons = tuple(tuple(polygon) for polygon in polygons if len(polygon) >= 3)
    if not polygons:
        return ()
    minimum_y = math.floor(min(point[1] for polygon in polygons for point in polygon) / step) * step
    maximum_y = math.ceil(max(point[1] for polygon in polygons for point in polygon) / step) * step
    bounds = tuple(
        (
            polygon,
            min(point[1] for point in polygon),
            max(point[1] for point in polygon),
        )
        for polygon in polygons
    )
    bands = []
    band_bottom = minimum_y
    while band_bottom < maximum_y:
        band_top = min(band_bottom + step, maximum_y)
        sample_y = (band_bottom + band_top) * 0.5
        intervals = merge_intervals(
            interval
            for polygon, bottom, top in bounds
            if bottom <= sample_y < top
            for interval in _scanline_intervals(polygon, sample_y)
        )
        bands.append((band_bottom, band_top, intervals))
        band_bottom = band_top
    return tuple(bands)


def scanline_band_triangles(bands):
    triangles = []
    for band_bottom, band_top, intervals in bands:
        for left, right in intervals:
            if right - left <= 1e-8:
                continue
            triangles.extend(
                (
                    (left, band_bottom),
                    (right, band_bottom),
                    (right, band_top),
                    (left, band_bottom),
                    (right, band_top),
                    (left, band_top),
                )
            )
    return tuple(triangles)


def subtract_intervals(intervals, covered):
    difference = []
    for left, right in intervals:
        position = left
        for cover_left, cover_right in covered:
            if cover_right <= position:
                continue
            if cover_left >= right:
                break
            if cover_left > position:
                difference.append((position, min(cover_left, right)))
            position = max(position, cover_right)
            if position >= right:
                break
        if position < right:
            difference.append((position, right))
    return tuple(difference)


def _closed_edge_loops(edges):
    def point_key(point):
        return round(point[0], 8), round(point[1], 8)

    adjacency = {}
    keyed_edges = []
    points = {}
    for index, (start, end) in enumerate(edges):
        start_key = point_key(start)
        end_key = point_key(end)
        keyed_edges.append((start_key, end_key))
        points[start_key] = start
        points[end_key] = end
        adjacency.setdefault(start_key, []).append((index, end_key))
        adjacency.setdefault(end_key, []).append((index, start_key))
    unused = set(range(len(keyed_edges)))
    loops = []
    while unused:
        edge_index = next(iter(unused))
        start_key, current_key = keyed_edges[edge_index]
        unused.remove(edge_index)
        loop = [points[start_key], points[current_key]]
        while current_key != start_key:
            candidates = (
                candidate
                for candidate in adjacency[current_key]
                if candidate[0] in unused
            )
            try:
                edge_index, next_key = next(candidates)
            except StopIteration:
                break
            unused.remove(edge_index)
            current_key = next_key
            loop.append(points[current_key])
        if len(loop) > 2:
            loops.append(tuple(loop))
    return tuple(loops)


def scanline_outline_segments(bands):
    """Return only the dashed outer boundary of merged scanline bands."""
    if not bands:
        return ()
    edges = []
    for bottom, top, intervals in bands:
        for left, right in intervals:
            edges.extend(
                (
                    ((left, bottom), (left, top)),
                    ((right, bottom), (right, top)),
                )
            )
    boundaries = [
        (bands[0][0], (), bands[0][2]),
        *(
            (current[0], previous[2], current[2])
            for previous, current in zip(bands, bands[1:])
        ),
        (bands[-1][1], bands[-1][2], ()),
    ]
    for y, lower, upper in boundaries:
        for left, right in (
            *subtract_intervals(lower, upper),
            *subtract_intervals(upper, lower),
        ):
            edges.append(((left, y), (right, y)))
    return tuple(
        point
        for loop in _closed_edge_loops(edges)
        for point in dashed_line_segments(loop)
    )


def _point_on_segment(point, start, end, epsilon=1e-8):
    return (
        min(start[0], end[0]) - epsilon <= point[0] <= max(start[0], end[0]) + epsilon
        and min(start[1], end[1]) - epsilon
        <= point[1]
        <= max(start[1], end[1]) + epsilon
    )


def _segments_intersect(first_start, first_end, second_start, second_end):
    crosses = (
        _triangle_cross(first_start, first_end, second_start),
        _triangle_cross(first_start, first_end, second_end),
        _triangle_cross(second_start, second_end, first_start),
        _triangle_cross(second_start, second_end, first_end),
    )
    if (crosses[0] > 1e-8) != (crosses[1] > 1e-8) and (crosses[2] > 1e-8) != (
        crosses[3] > 1e-8
    ):
        return True
    return any(
        abs(cross) <= 1e-8 and _point_on_segment(point, start, end)
        for cross, point, start, end in (
            (crosses[0], second_start, first_start, first_end),
            (crosses[1], second_end, first_start, first_end),
            (crosses[2], first_start, second_start, second_end),
            (crosses[3], first_end, second_start, second_end),
        )
    )


def polygon_self_intersects(vertices, cell_size=32.0):
    vertices = tuple(tuple(float(value) for value in vertex) for vertex in vertices)
    if len(vertices) < 4:
        return False
    edges = tuple(zip(vertices, (*vertices[1:], vertices[0])))
    cells = {}
    last_edge = len(edges) - 1
    for edge_index, (start, end) in enumerate(edges):
        left = math.floor(min(start[0], end[0]) / cell_size)
        right = math.floor(max(start[0], end[0]) / cell_size)
        bottom = math.floor(min(start[1], end[1]) / cell_size)
        top = math.floor(max(start[1], end[1]) / cell_size)
        edge_cells = tuple(
            (x, y) for x in range(left, right + 1) for y in range(bottom, top + 1)
        )
        candidates = {
            candidate for cell in edge_cells for candidate in cells.get(cell, ())
        }
        for candidate in candidates:
            if abs(edge_index - candidate) <= 1 or {
                edge_index,
                candidate,
            } == {0, last_edge}:
                continue
            if _segments_intersect(start, end, *edges[candidate]):
                return True
        for cell in edge_cells:
            cells.setdefault(cell, []).append(edge_index)
    return False


def preview_fill_geometry(vertices):
    """Return fill triangles and dashed boundary for one merged polygon."""
    vertices = tuple(vertices)
    if len(vertices) < 3:
        outline = (*vertices, vertices[0]) if len(vertices) > 1 else ()
        return (), dashed_line_segments(outline)
    if not polygon_self_intersects(vertices):
        triangles = triangulated_polygon_vertices(vertices)
        if triangles:
            return triangles, dashed_line_segments((*vertices, vertices[0]))
    bands = scanline_fill_bands(vertices)
    return scanline_band_triangles(bands), scanline_outline_segments(bands)


def circle_vertices(center, radius, segments=32):
    """Return a closed screen-space circle without repeating its first point."""
    center_x, center_y = (float(value) for value in center)
    radius = float(radius)
    if radius <= 0.0 or segments < 3:
        raise ValueError("The brush circle is invalid")
    return tuple(
        (
            center_x + math.cos(index * math.tau / segments) * radius,
            center_y + math.sin(index * math.tau / segments) * radius,
        )
        for index in range(segments)
    )


def brush_footprint_polygons(path, radius):
    """Return circles and connecting strips defining one Brush footprint."""
    points = tuple(path)
    if not points:
        return ()
    polygons = [circle_vertices(points[0], radius)]
    for start, end in zip(points, points[1:]):
        delta_x = end[0] - start[0]
        delta_y = end[1] - start[1]
        length = math.hypot(delta_x, delta_y)
        if length <= 1e-8:
            continue
        normal_x = -delta_y * radius / length
        normal_y = delta_x * radius / length
        polygons.append(
            (
                (start[0] + normal_x, start[1] + normal_y),
                (end[0] + normal_x, end[1] + normal_y),
                (end[0] - normal_x, end[1] - normal_y),
                (start[0] - normal_x, start[1] - normal_y),
            )
        )
        polygons.append(circle_vertices(end, radius))
    return tuple(polygons)
