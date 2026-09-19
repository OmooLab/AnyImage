"""View3D projection, gestures, tool settings, and overlay drawing."""

import json
import math
import time

import bpy

from .image import (
    image_empty_bounds,
    is_image_empty,
    require_image_empty,
    is_animated_image,
)
from .selection import ImageEditWarning, SelectionPath

MIN_PATH_DISTANCE = 2.0


def image_edit_selection_keymap(*, deselect_on_empty=True):
    return (
        (
            "view3d.select",
            {"type": "LEFTMOUSE", "value": "CLICK"},
            {"properties": [("deselect_all", deselect_on_empty)]},
        ),
        (
            "view3d.select",
            {"type": "LEFTMOUSE", "value": "CLICK", "shift": True},
            {"properties": [("toggle", True)]},
        ),
    )


def image_edit_drag_keymap(
    operator_id,
    properties=None,
    *,
    deselect_on_empty=True,
):
    return (
        (
            operator_id,
            {"type": "LEFTMOUSE", "value": "CLICK_DRAG"},
            properties,
        ),
        *image_edit_selection_keymap(deselect_on_empty=deselect_on_empty),
    )


def image_edit_point_keymap(operator_id, properties=None):
    return (
        (
            operator_id,
            {"type": "LEFTMOUSE", "value": "PRESS"},
            properties,
        ),
        image_edit_selection_keymap()[1],
    )


def simplify_screen_path(path):
    pixels = []
    for point in path:
        point = (float(point[0]), float(point[1]))
        if not pixels or math.dist(point, pixels[-1]) >= MIN_PATH_DISTANCE:
            pixels.append(point)
    return pixels


def screen_path_to_image_pixels(
    path,
    view_region,
    view3d,
    matrix_world,
    local_bounds,
    image_size,
    *,
    simplify=True,
):
    from bpy_extras import view3d_utils

    inverse = matrix_world.inverted()
    x_min, x_max, y_min, y_max = local_bounds
    image_width, image_height = image_size
    local_width = x_max - x_min
    local_height = y_max - y_min
    pixels = []
    screen_points = simplify_screen_path(path) if simplify else path
    for point in screen_points:
        ray_origin = inverse @ view3d_utils.region_2d_to_origin_3d(
            view_region,
            view3d,
            point,
        )
        ray_direction = inverse.to_3x3() @ view3d_utils.region_2d_to_vector_3d(
            view_region,
            view3d,
            point,
        )
        if abs(ray_direction.z) <= 1e-10:
            raise ValueError("The Image Empty is edge-on to the current view")
        distance = -ray_origin.z / ray_direction.z
        local = ray_origin + ray_direction * distance
        pixels.append(
            (
                (local.x - x_min) * image_width / local_width,
                (y_max - local.y) * image_height / local_height,
            )
        )
    return pixels


def serialize_matrix(matrix):
    return json.dumps(
        [float(matrix[row][column]) for row in range(4) for column in range(4)],
        separators=(",", ":"),
    )


def deserialize_matrix(data):
    from mathutils import Matrix

    values = json.loads(data)
    if len(values) != 16:
        raise ValueError("The stored Image Empty transform is invalid")
    return Matrix(tuple(tuple(values[row * 4 : row * 4 + 4]) for row in range(4)))


def drawing_in_region(area_pointer, region_pointer):
    area = getattr(bpy.context, "area", None)
    region = getattr(bpy.context, "region", None)
    return (
        area is not None
        and region is not None
        and area.as_pointer() == area_pointer
        and region.as_pointer() == region_pointer
    )


def report_image_edit_exception(operator, error):
    level = "WARNING" if isinstance(error, ImageEditWarning) else "ERROR"
    operator.report({level}, str(error))


def image_edit_poll(context):
    return context.area is not None and context.area.type == "VIEW_3D"


def resolve_image_edit_click(context, event, report):
    """Resolve the first click into source selection or image editing."""
    active_object = context.active_object
    try:
        bpy.ops.view3d.select(
            location=(event.mouse_region_x, event.mouse_region_y),
            extend=False,
            deselect_all=False,
        )
    except RuntimeError:
        pass
    clicked_object = context.active_object
    if clicked_object != active_object:
        return clicked_object, False
    try:
        return active_image_edit_source(context), True
    except ImageEditWarning as error:
        report({"WARNING"}, str(error))
        return None, False


def active_image_edit_source(context):
    """Return the selected active Image Empty used by image edit tools."""
    source_object = context.active_object
    if (
        not is_image_empty(source_object)
        or source_object not in context.selected_objects
    ):
        raise ImageEditWarning(
            "Select an active Image Empty to use an Image tool"
        )
    return source_object


def active_view3d_tool_id(context):
    tools = getattr(getattr(context, "workspace", None), "tools", None)
    from_mode = getattr(tools, "from_space_view3d_mode", None)
    if not callable(from_mode):
        return None
    try:
        tool = from_mode(getattr(context, "mode", "OBJECT"), create=False)
    except (RuntimeError, TypeError):
        return None
    return getattr(tool, "idname", None)


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


def draw_dashed_line(
    vertices,
    color=(1.0, 1.0, 1.0, 0.9),
    segments=None,
):
    import gpu
    from gpu_extras.batch import batch_for_shader

    if segments is None:
        segments = dashed_line_segments(vertices)
    if not segments:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": segments})
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(1.0)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


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


def _merge_intervals(intervals):
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
        intervals = _merge_intervals(
            interval
            for polygon, bottom, top in bounds
            if bottom <= sample_y < top
            for interval in _scanline_intervals(polygon, sample_y)
        )
        bands.append((band_bottom, band_top, intervals))
        band_bottom = band_top
    return tuple(bands)


def _scanline_band_triangles(bands):
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


def _subtract_intervals(intervals, covered):
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
            *_subtract_intervals(lower, upper),
            *_subtract_intervals(upper, lower),
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
    return _scanline_band_triangles(bands), scanline_outline_segments(bands)


def draw_polygon_fill(
    vertices,
    triangles=None,
    color=(1.0, 1.0, 1.0, 0.16),
):
    import gpu
    from gpu_extras.batch import batch_for_shader

    if triangles is None:
        triangles = triangulated_polygon_vertices(vertices)
    if not triangles:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRIS", {"pos": triangles})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


LASSO_POINT_DISTANCE = 2.0
LASSO_SIMPLIFY_TOLERANCE = 0.75
POLYLINE_CLOSE_RADIUS = 15.0
POLYLINE_CLOSE_MIN_RADIUS = 1.0
POLYLINE_DOUBLE_CLICK_DISTANCE = 5.0
POLYLINE_DOUBLE_CLICK_INTERVAL = 0.35


def polyline_close_radius(ui_scale=1.0):
    """Return the screen-space radius that completes a Polyline."""
    return POLYLINE_CLOSE_RADIUS * float(ui_scale)


def polyline_close_indicator_radius(distance, ui_scale=1.0):
    """Return Blender's progressive Polyline start-circle radius."""
    scale = float(ui_scale)
    close_radius = polyline_close_radius(scale)
    hint_distance = close_radius * close_radius
    distance = float(distance)
    if distance >= hint_distance:
        return None
    factor = max(0.0, distance / hint_distance)
    smooth = factor * factor * (3.0 - 2.0 * factor)
    minimum_radius = POLYLINE_CLOSE_MIN_RADIUS * scale
    return close_radius + (minimum_radius - close_radius) * smooth


def is_polyline_double_click(
    previous_point,
    previous_time,
    point,
    current_time,
    *,
    ui_scale=1.0,
    interval=POLYLINE_DOUBLE_CLICK_INTERVAL,
):
    """Return whether two raw presses form a Polyline double-click."""
    if previous_point is None or previous_time is None:
        return False
    elapsed = float(current_time) - float(previous_time)
    return (
        0.0 <= elapsed <= float(interval)
        and math.dist(point, previous_point)
        <= POLYLINE_DOUBLE_CLICK_DISTANCE * float(ui_scale)
    )


def append_lasso_point(path, point, samples):
    """Append a sample with bounded error over the complete active segment."""
    point = (float(point[0]), float(point[1]))
    if not path:
        path.append(point)
        samples[:] = [point]
        return True
    if point == path[-1]:
        return False
    previous = path[-1]
    if len(path) >= 2 and 1 < len(samples) < 128:
        anchor = path[-2]
        dx, dy = point[0] - anchor[0], point[1] - anchor[1]
        squared = dx * dx + dy * dy
        if squared > 0:
            def within_segment(sample):
                x, y = sample[0] - anchor[0], sample[1] - anchor[1]
                factor = (x * dx + y * dy) / squared
                return (0 <= factor <= 1 and
                        abs(x * dy - y * dx) <= LASSO_SIMPLIFY_TOLERANCE * math.sqrt(squared))
            if all(within_segment(sample) for sample in samples):
                path[-1] = point
                samples.append(point)
                return True
    path.append(point)
    samples[:] = [previous, point]
    return True


def rectangle_screen_path(start, end):
    x0, y0 = start
    x1, y1 = end
    if abs(x1 - x0) < 2.0 or abs(y1 - y0) < 2.0:
        return ()
    left, right = sorted((float(x0), float(x1)))
    bottom, top = sorted((float(y0), float(y1)))
    return ((left, top), (right, top), (right, bottom), (left, bottom))


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


def draw_circle_outline(
    center,
    radius,
    color=(1.0, 1.0, 1.0, 0.95),
    line_width=1.0,
):
    import gpu
    from gpu_extras.batch import batch_for_shader

    vertices = circle_vertices(center, radius)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(
        shader,
        "LINE_STRIP",
        {"pos": (*vertices, vertices[0])},
    )
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(line_width)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set("NONE")


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


def draw_polyline_close_indicator(center, radius, ui_scale=1.0):
    draw_circle_outline(center, radius, (1.0, 1.0, 1.0, 0.8))
    draw_circle_outline(
        center,
        radius + float(ui_scale),
        (0.4, 0.4, 0.4, 0.8),
    )


class BrushPreview:
    """Cache fixed screen rows for a sealed stroke prefix and a movable tail."""

    rows_per_chunk = 32
    step = 2.0

    def __init__(self):
        self.prefix = {}
        self.tail = {}
        self.coverage = {}
        self.geometry = {}
        self.batches = {}
        self.shader = None
        self.count = 0
        self.key = None

    def _polygon_rows(self, polygons):
        return {
            round(bottom / self.step): intervals
            for bottom, _top, intervals in scanline_union_bands(polygons, self.step)
            if intervals
        }

    def update(self, path, radius):
        key = (len(path), tuple(path[-2:]), radius)
        if key == self.key:
            return
        self.key = key
        changed = set(self.tail)
        target = max(1, len(path) - 1)
        for index in range(self.count, target):
            polygons = (circle_vertices(path[0], radius),) if index == 0 else (
                brush_footprint_polygons(path[index - 1:index + 1], radius)[1:]
            )
            for row, intervals in self._polygon_rows(polygons).items():
                self.prefix[row] = _merge_intervals((*self.prefix.get(row, ()), *intervals))
                changed.add(row)
        self.count = target
        self.tail = self._polygon_rows(
            brush_footprint_polygons(path[-2:], radius)[1:]
        ) if len(path) > 1 else {}
        changed.update(self.tail)
        chunks = set()
        for row in changed:
            intervals = _merge_intervals((*self.prefix.get(row, ()), *self.tail.get(row, ())))
            if intervals == self.coverage.get(row, ()):
                continue
            if intervals:
                self.coverage[row] = intervals
            else:
                self.coverage.pop(row, None)
            chunks.update((row // self.rows_per_chunk, (row + 1) // self.rows_per_chunk))
        for chunk in chunks:
            self.geometry[chunk] = self._chunk_geometry(chunk)
            self.batches.pop(chunk, None)

    def _chunk_geometry(self, chunk):
        bands, outline = [], []
        for row in range(chunk * self.rows_per_chunk, (chunk + 1) * self.rows_per_chunk):
            bottom = row * self.step
            intervals = self.coverage.get(row, ())
            lower = self.coverage.get(row - 1, ())
            bands.append((bottom, bottom + self.step, intervals))
            for left, right in intervals:
                for x in (left, right):
                    outline.extend(dashed_line_segments(
                        ((x, bottom), (x, bottom + self.step)), offset=bottom
                    ))
            for left, right in (*_subtract_intervals(intervals, lower),
                                *_subtract_intervals(lower, intervals)):
                outline.extend(dashed_line_segments(
                    ((left, bottom), (right, bottom)), offset=left
                ))
        return _scanline_band_triangles(bands), tuple(outline)

    def draw(self, color):
        import gpu
        from gpu_extras.batch import batch_for_shader

        if self.shader is None:
            self.shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        shader = self.shader
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(1.0)
        try:
            shader.bind()
            for chunk, (triangles, outline) in self.geometry.items():
                if chunk not in self.batches:
                    self.batches[chunk] = tuple(
                        batch_for_shader(shader, kind, {"pos": vertices}) if vertices else None
                        for kind, vertices in (("TRIS", triangles), ("LINES", outline))
                    )
                fill, line = self.batches[chunk]
                if fill is not None:
                    shader.uniform_float("color", color)
                    fill.draw(shader)
                if line is not None:
                    shader.uniform_float("color", (1.0, 1.0, 1.0, 0.9))
                    line.draw(shader)
        finally:
            gpu.state.blend_set("NONE")


class ImageGesture:
    active_tool_id = None
    resolve_on_press = False
    _path = None
    _cursor = None
    _handle = None
    _preview_polygon = None
    _fill_triangles = ()
    _brush_preview = None
    _outline_segments = ()
    _area_pointer = 0
    _region_pointer = 0
    _path_samples = None
    _ui_scale = 1.0

    @classmethod
    def poll(cls, context):
        return image_edit_poll(context)

    def _draw_selection(self):
        if not self._path or not drawing_in_region(
            self._area_pointer, self._region_pointer
        ):
            return
        color = ((1.0, 0.25, 0.2, 0.16) if getattr(self, "mode", "SET") == "SUBTRACT"
                 else (1.0, 1.0, 1.0, 0.16))
        if self.gesture == "BRUSH":
            if self._brush_preview is None:
                self._brush_preview = BrushPreview()
            self._brush_preview.update(self._path, self.radius)
            self._brush_preview.draw(color)
            return
        polygon = ImageGesture._screen_path(self)
        if polygon != self._preview_polygon:
            self._preview_polygon = polygon
            self._fill_triangles, self._outline_segments = preview_fill_geometry(polygon)
        if self._fill_triangles:
            draw_polygon_fill(polygon, self._fill_triangles, color)
        if self._outline_segments:
            draw_dashed_line((), segments=self._outline_segments)
        if (
            self.gesture == "POLYLINE"
            and len(self._path) >= 3
            and self._cursor is not None
        ):
            ui_scale = getattr(self, "_ui_scale", 1.0)
            radius = polyline_close_indicator_radius(
                math.dist(self._cursor, self._path[0]),
                ui_scale,
            )
            if radius is not None:
                draw_polyline_close_indicator(
                    self._path[0],
                    radius,
                    ui_scale,
                )

    def _screen_path(self):
        if self.gesture != "POLYLINE" or self._cursor is None:
            return tuple(self._path)
        if self._cursor == self._path[-1]:
            return tuple(self._path)
        return (*self._path, self._cursor)

    def _set_status(self, context):
        context.workspace.status_text_set(
            f"{self.gesture.title()}: drag and release; RMB or Esc cancels"
        )

    def _finish(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        self._path = None
        self._path_samples = None
        self._cursor = None
        self._preview_polygon = None
        self._fill_triangles = ()
        self._outline_segments = ()
        self._brush_preview = None
        context.workspace.status_text_set(None)
        if context.area is not None:
            context.area.tag_redraw()

    def cancel(self, context):
        self._finish(context)

    def _submit_selection_path(self, _context, _selection_path):
        raise NotImplementedError

    def _complete_brush(self, _context, _source_object, _matrix):
        raise NotImplementedError

    def _read_gesture_settings(self, _context):
        pass

    def invoke(self, context, event):
        self._read_gesture_settings(context)
        if self.resolve_on_press:
            source_object, should_edit = resolve_image_edit_click(
                context, event, self.report
            )
            if not should_edit:
                return {"FINISHED"} if source_object is not None else {"CANCELLED"}
        else:
            try:
                source_object = active_image_edit_source(context)
            except ImageEditWarning as error:
                report_image_edit_exception(self, error)
                return {"CANCELLED"}
        if source_object is None:
            return {"CANCELLED"}
        if is_animated_image(source_object.data):
            self.report({"WARNING"}, "Image gestures only support a still image")
            return {"CANCELLED"}
        self.source_object_name = source_object.name
        self.source_matrix_data = serialize_matrix(source_object.matrix_world)
        point = (float(event.mouse_region_x), float(event.mouse_region_y))
        self._path = [point]
        self._cursor = point
        self._preview_polygon = None
        self._fill_triangles = ()
        self._brush_preview = None
        self._outline_segments = ()
        self._area_pointer = context.area.as_pointer()
        self._region_pointer = context.region.as_pointer()
        self._path_samples = [point]
        preferences = getattr(context, "preferences", None)
        system = getattr(preferences, "system", None)
        self._ui_scale = float(getattr(system, "ui_scale", 1.0) or 1.0)
        inputs = getattr(preferences, "inputs", None)
        double_click_time = float(
            getattr(inputs, "double_click_time", POLYLINE_DOUBLE_CLICK_INTERVAL * 1000)
            or POLYLINE_DOUBLE_CLICK_INTERVAL * 1000
        )
        self._polyline_double_click_interval = double_click_time / 1000.0
        self._last_polyline_click_point = point
        self._last_polyline_click_time = time.monotonic()
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_selection, (), "WINDOW", "POST_PIXEL"
        )
        self._set_status(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def _complete(self, context):
        source_object = require_image_empty(self.source_object_name)
        matrix = deserialize_matrix(self.source_matrix_data)
        if self.gesture == "BRUSH":
            result = self._complete_brush(context, source_object, matrix)
            self._finish(context)
            return result
        path = tuple(self._path)
        if len(path) < 3:
            self._finish(context)
            return {"CANCELLED"}
        selection_path = screen_path_to_image_pixels(
            path,
            context.region,
            context.region_data,
            matrix,
            image_empty_bounds(source_object),
            tuple(source_object.data.size),
        )
        selection_path = SelectionPath(
            points=selection_path,
        )
        self._finish(context)
        return self._submit_selection_path(context, selection_path)

    def _cancel_and_finish(self, context):
        self._finish(context)
        return {"CANCELLED"}

    def _confirm_polyline(self, context):
        if len(self._path) < 3:
            return {"RUNNING_MODAL"}
        try:
            return self._complete(context)
        except (RuntimeError, TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return self._cancel_and_finish(context)

    def _modal_polyline(self, context, event):
        if event.type == "BACK_SPACE" and event.value == "PRESS":
            if len(self._path) > 1:
                self._path.pop()
            self._cursor = self._path[-1]
            self._last_polyline_click_point = None
            self._last_polyline_click_time = None
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            return self._confirm_polyline(context)
        if event.type == "LEFTMOUSE" and event.value == "DOUBLE_CLICK":
            return self._confirm_polyline(context)
        if event.type == "MOUSEMOVE":
            self._cursor = (
                float(event.mouse_region_x),
                float(event.mouse_region_y),
            )
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point = (float(event.mouse_region_x), float(event.mouse_region_y))
            if (
                len(self._path) >= 3
                and math.dist(point, self._path[0])
                <= polyline_close_radius(getattr(self, "_ui_scale", 1.0))
            ):
                return self._confirm_polyline(context)
            current_time = time.monotonic()
            if len(self._path) >= 3 and is_polyline_double_click(
                getattr(self, "_last_polyline_click_point", None),
                getattr(self, "_last_polyline_click_time", None),
                point,
                current_time,
                ui_scale=getattr(self, "_ui_scale", 1.0),
                interval=getattr(
                    self,
                    "_polyline_double_click_interval",
                    POLYLINE_DOUBLE_CLICK_INTERVAL,
                ),
            ):
                return self._confirm_polyline(context)
            if math.dist(point, self._path[-1]) >= LASSO_POINT_DISTANCE:
                self._path.append(point)
            self._last_polyline_click_point = point
            self._last_polyline_click_time = current_time
            self._cursor = point
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def modal(self, context, event):
        active_tool = active_view3d_tool_id(context)
        expected_tool = self.active_tool_id
        if active_tool is not None and active_tool != expected_tool:
            return self._cancel_and_finish(context)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self._cancel_and_finish(context)
        if self.gesture == "POLYLINE":
            return self._modal_polyline(context, event)
        if event.type == "MOUSEMOVE":
            point = (float(event.mouse_region_x), float(event.mouse_region_y))
            if not append_lasso_point(self._path, point, self._path_samples):
                return {"RUNNING_MODAL"}
            self._cursor = point
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            point = (float(event.mouse_region_x), float(event.mouse_region_y))
            append_lasso_point(self._path, point, self._path_samples)
            self._cursor = point
            try:
                return self._complete(context)
            except (RuntimeError, TypeError, ValueError) as error:
                report_image_edit_exception(self, error)
                return self._cancel_and_finish(context)
        return {"PASS_THROUGH"}
