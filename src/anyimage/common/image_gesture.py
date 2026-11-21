"""Shared Cutout and Mask gestures and their viewport previews."""

import math
import time

import bpy

from . import polygon as polygon_geometry
from .image import image_empty_bounds, is_animated_image, require_image_empty
from .selection import ImageEditWarning, SelectionPath
from .tool_status import set_tool_status
from .viewport import (
    active_image_edit_source,
    active_view3d_tool_id,
    clicked_image_source,
    draw_dashed_line,
    draw_polygon_fill,
    draw_polygon_outline,
    drawing_in_region,
    image_edit_poll,
    report_image_edit_exception,
    screen_path_to_image_pixels,
)

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


def draw_polyline_close_indicator(center, radius, ui_scale=1.0):
    draw_polygon_outline(polygon_geometry.circle_vertices(center, radius), (1.0, 1.0, 1.0, 0.8))
    draw_polygon_outline(
        polygon_geometry.circle_vertices(center, radius + float(ui_scale)),
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
            for bottom, _top, intervals in polygon_geometry.scanline_union_bands(polygons, self.step)
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
            polygons = (polygon_geometry.circle_vertices(path[0], radius),) if index == 0 else (
                polygon_geometry.brush_footprint_polygons(path[index - 1:index + 1], radius)[1:]
            )
            for row, intervals in self._polygon_rows(polygons).items():
                self.prefix[row] = polygon_geometry.merge_intervals((*self.prefix.get(row, ()), *intervals))
                changed.add(row)
        self.count = target
        self.tail = self._polygon_rows(
            polygon_geometry.brush_footprint_polygons(path[-2:], radius)[1:]
        ) if len(path) > 1 else {}
        changed.update(self.tail)
        chunks = set()
        for row in changed:
            intervals = polygon_geometry.merge_intervals((*self.prefix.get(row, ()), *self.tail.get(row, ())))
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
                    outline.extend(polygon_geometry.dashed_line_segments(
                        ((x, bottom), (x, bottom + self.step)), offset=bottom
                    ))
            for left, right in (*polygon_geometry.subtract_intervals(intervals, lower),
                                *polygon_geometry.subtract_intervals(lower, intervals)):
                outline.extend(polygon_geometry.dashed_line_segments(
                    ((left, bottom), (right, bottom)), offset=left
                ))
        return polygon_geometry.scanline_band_triangles(bands), tuple(outline)

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
            self._fill_triangles, self._outline_segments = polygon_geometry.preview_fill_geometry(polygon)
        if self._fill_triangles:
            self._draw_selection_fill(color)
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

    def _draw_selection_fill(self, color):
        draw_polygon_fill(self._preview_polygon, self._fill_triangles, color)

    def _screen_path(self):
        if self.gesture != "POLYLINE" or self._cursor is None:
            return tuple(self._path)
        if self._cursor == self._path[-1]:
            return tuple(self._path)
        return (*self._path, self._cursor)

    def _set_gesture_status(self, context):
        if self.gesture == "POLYLINE":
            set_tool_status(
                context,
                ("Add Point", "LEFTMOUSE"),
                (self.finish_label, "RET"),
                ("Remove Point", "RIGHTMOUSE"),
                cancel_event="ESC",
            )
        else:
            set_tool_status(context, (self.finish_label, "DRAG"))

    def _finish(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        self._source_matrix = None
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

    def _submit_selection_path(self, _context, _source_object, _selection_path):
        raise NotImplementedError

    def _complete_brush(self, _context, _source_object, _matrix):
        raise NotImplementedError

    def invoke(self, context, event):
        self._read_gesture_settings(context)
        start_event = "PRESS" if self.gesture == "POLYLINE" else "CLICK_DRAG"
        if event.value != start_event:
            return {"PASS_THROUGH"}
        if start_event == "CLICK_DRAG":
            try:
                source_object = active_image_edit_source(context)
            except ImageEditWarning as error:
                self.report({"WARNING"}, str(error))
                return {"CANCELLED"}
            point = (event.mouse_prev_press_x - context.region.x,
                     event.mouse_prev_press_y - context.region.y)
        else:
            source_object = clicked_image_source(context, event)
            if source_object is None:
                return {"PASS_THROUGH"}
            point = (event.mouse_region_x, event.mouse_region_y)
        if is_animated_image(source_object.data):
            self.report({"WARNING"}, "Image gestures only support a still image")
            return {"CANCELLED"}
        self.source_object_name = source_object.name
        self._source_matrix = source_object.matrix_world.copy()
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
        self._set_gesture_status(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def _complete(self, context):
        source_object = require_image_empty(self.source_object_name)
        if self.gesture == "BRUSH":
            result = self._complete_brush(context, source_object, self._source_matrix)
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
            self._source_matrix,
            image_empty_bounds(source_object),
            tuple(source_object.data.size),
        )
        selection_path = SelectionPath(
            points=selection_path,
        )
        self._finish(context)
        return self._submit_selection_path(context, source_object, selection_path)

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
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            if len(self._path) == 1:
                return self._cancel_and_finish(context)
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
        if event.type == "ESC" and event.value == "PRESS":
            return self._cancel_and_finish(context)
        if self.gesture == "POLYLINE":
            return self._modal_polyline(context, event)
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            return self._cancel_and_finish(context)
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
