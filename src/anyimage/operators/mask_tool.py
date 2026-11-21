import bpy

from ..common import polygon as polygon_geometry
from ..common.image import (
    create_image_edit_result,
    image_empty_bounds,
    image_rgba,
    replace_empty_image,
    require_image_empty,
)
from ..common.selection import (
    rasterize_selection_path,
    rasterize_selection_union,
    SelectionPath,
)
from ..common.image_gesture import ImageGesture
from ..common.viewport import report_image_edit_exception, screen_path_to_image_pixels
from ..properties import (
    mask_gesture_property,
    mask_mode_property,
    mask_radius_property,
)

MASK_TOOL_ID = "anyimage.mask"


def apply_alpha_mask(source_rgba, selection_mask, mode):
    """Apply one Selection Mask to current Alpha without changing the canvas."""
    import numpy as np

    rgba = np.asarray(source_rgba, dtype=np.float32).copy()
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("The source image must contain RGBA pixels")
    alpha = rgba[..., 3]
    region, values = selection_mask.region_in(alpha)
    if mode == "SET":
        selected = region * values
        alpha.fill(0)
        region[:] = selected
    elif mode == "EXTEND":
        np.maximum(region, values, out=region)
    elif mode == "SUBTRACT":
        region *= 1.0 - values
    else:
        raise ValueError(f"Unsupported Mask mode: {mode}")
    np.clip(alpha, 0.0, 1.0, out=alpha)
    return np.flipud(rgba).ravel()


def rasterize_brush_path(image_size, path, radius, project_path):
    """Project the shared Brush footprint and antialias its complete union."""
    paths = (
        SelectionPath(points=project_path(polygon))
        for polygon in polygon_geometry.brush_footprint_polygons(path, radius)
    )
    return rasterize_selection_union(image_size, paths, antialias=True)


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


class EditImageAlpha(ImageGesture, bpy.types.Operator):
    bl_idname = "anyimage.edit_image_alpha"
    bl_label = "Edit Image Alpha"
    bl_description = "Hide or reveal image areas with a lasso, brush, or polyline."
    bl_options = {"UNDO"}
    finish_label = "Apply Mask"
    active_tool_id = MASK_TOOL_ID
    _brush_preview = None

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    gesture: mask_gesture_property()
    mode: mask_mode_property()
    radius: mask_radius_property()

    def _read_gesture_settings(self, context):
        settings = context.scene.anyimage_settings
        self.gesture = str(settings.mask_gesture)
        self.mode = str(settings.mask_mode)
        self.radius = int(settings.mask_radius)

    def _submit_selection_path(self, context, source_object, selection_path):
        selection_mask = rasterize_selection_path(
            tuple(source_object.data.size),
            selection_path,
            antialias=True,
        )
        return self._apply_mask(context, source_object, selection_mask)

    def _draw_preview(self, color):
        if self.gesture != "BRUSH":
            return super()._draw_preview(color)
        if self._brush_preview is None:
            self._brush_preview = BrushPreview()
        self._brush_preview.update(self._path, self.radius)
        self._brush_preview.draw(color)

    def _finish(self, context):
        self._brush_preview = None
        super()._finish(context)

    def _complete(self, context):
        if self.gesture != "BRUSH":
            return super()._complete(context)
        source_object = require_image_empty(self.source_object_name)
        image_size = tuple(source_object.data.size)
        local_bounds = image_empty_bounds(source_object)
        selection_mask = rasterize_brush_path(
            image_size,
            self._path,
            self.radius,
            lambda path: screen_path_to_image_pixels(
                path,
                context.region,
                context.region_data,
                self._source_matrix,
                local_bounds,
                image_size,
                simplify=False,
            ),
        )
        self._finish(context)
        return self._apply_mask(context, source_object, selection_mask)

    def _apply_mask(self, context, source_object, selection_mask):
        try:
            source_image = source_object.data
            pixels = apply_alpha_mask(
                image_rgba(source_image),
                selection_mask,
                self.mode,
            )
            result_image = create_image_edit_result(
                source_image,
                pixels,
                tuple(source_image.size),
            )
            replace_empty_image(source_object, result_image)
        except (RuntimeError, TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        return {"FINISHED"}
