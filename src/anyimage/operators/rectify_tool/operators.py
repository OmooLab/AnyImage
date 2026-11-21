"""Rectify interaction and Blender image replacement."""

import json
import math

import bpy

from ...common.image_preview import (
    draw_preview_caption,
    preview_draw_bounds,
    create_preview_texture,
    draw_preview_texture,
)
from ...common.tool_status import set_tool_status
from ...common.viewport import (
    active_view3d_tool_id,
    draw_dashed_line,
    draw_polygon_fill,
    draw_polygon_outline,
    drawing_in_region,
    image_edit_poll,
    report_image_edit_exception,
    clicked_image_source,
    screen_path_to_image_pixels,
)
from ...common.selection import ImageEditWarning
from ...common.object import read_conversion_source, require_conversion_source
from ...common.image import image_content_signature, create_image_edit_result, image_pixels, image_empty_bounds, replace_empty_image, require_image_empty, is_animated_image
from ...common.projective_image import premultiplied_rgba, warp_projective_pixels
from ...common.color_space import image_rgba_to_linear, linear_rgba_to_image
from .geometry import (
    MAX_INTERACTIVE_ASPECT,
    MIN_INTERACTIVE_ASPECT,
    canonical_perspective_quad,
    extract_perspective_pixels,
    perspective_quad_aspect,
    perspective_quad_overlaps_image,
    validate_perspective_quad,
    validated_corner_ring,
)
from .preview import (
    PREVIEW_TEXTURE_SIZE,
    aspect_ratio_from_mouse,
    aspect_ratio_label,
    interactive_preview_polygon,
    snapped_aspect_ratio,
)


MIN_QUAD_AREA = 16.0
RECTIFY_TOOL_ID = "anyimage.rectify"


def _rectify_sampling_pixels(image, pixels):
    linear = image_rgba_to_linear(image, pixels.reshape(-1, 4))
    return premultiplied_rgba(linear, image.size)


class RectifyImagePerspective(bpy.types.Operator):
    bl_idname = "anyimage.rectify_image_perspective"
    bl_label = "Rectify Image Perspective"
    bl_description = "Select four corners of an image area to correct its perspective into a rectangle."
    bl_options = {"REGISTER", "UNDO"}

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    quad_json: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    aspect_ratio: bpy.props.FloatProperty(
        default=1.0,
        min=MIN_INTERACTIVE_ASPECT,
        max=MAX_INTERACTIVE_ASPECT,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    _points = None
    _cursor = None
    _handle = None
    _timer = None
    _phase = "POINTS"
    _preview_texture = None
    _source_premultiplied = None
    _source_object = None
    _source_image = None
    _source_signature = None
    _initial_aspect_ratio = 1.0
    _aspect_preset_label = None
    _aspect_anchor_x = 0.0
    _area_pointer = 0
    _region_pointer = 0

    @classmethod
    def poll(cls, context):
        return image_edit_poll(context)

    def _draw_preview(self):
        if self._preview_texture is None:
            return
        region = bpy.context.region
        bounds = preview_draw_bounds(
            (region.width, region.height), self.aspect_ratio,
        )
        draw_preview_texture(self._preview_texture, bounds)
        left, bottom, width, height = bounds
        right, top = left + width, bottom + height
        draw_polygon_outline(
            ((left, bottom), (right, bottom), (right, top), (left, top)),
            (0.8, 0.8, 0.8, 0.85),
        )
        draw_preview_caption(region, aspect_ratio_label(self.aspect_ratio, self._aspect_preset_label))

    def _draw_overlay(self):
        if not self._points or not drawing_in_region(
            self._area_pointer, self._region_pointer
        ):
            return
        if self._phase == "ASPECT":
            self._draw_preview()
            return
        vertices = list(interactive_preview_polygon(self._points, self._cursor))
        draw_polygon_fill(vertices)
        if len(vertices) > 2:
            vertices.append(vertices[0])
        draw_dashed_line(vertices)

    def _set_point_status(self, context):
        label = bpy.app.translations.pgettext_iface("Place Corner {index}/4")
        set_tool_status(
            context,
            (label.format(index=len(self._points) + 1), "LEFTMOUSE"),
            ("Remove Point", "RIGHTMOUSE"),
            cancel_event="ESC",
        )

    def _set_aspect_status(self, context):
        set_tool_status(
            context,
            ("Snap to Preset", "LEFT_CTRL"),
            ("Confirm", "LEFTMOUSE"),
        )

    def _update_aspect(self, context, event):
        ratio = aspect_ratio_from_mouse(
            self._initial_aspect_ratio,
            float(event.mouse_x) - self._aspect_anchor_x,
        )
        if event.ctrl:
            self.aspect_ratio, self._aspect_preset_label = snapped_aspect_ratio(ratio)
        else:
            self.aspect_ratio = ratio
            self._aspect_preset_label = None
        context.area.tag_redraw()

    def _finish(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._preview_texture = None
        self._source_premultiplied = None
        context.workspace.status_text_set(None)
        if context.area is not None:
            context.area.tag_redraw()

    def cancel(self, context):
        self._finish(context)

    def invoke(self, context, event):
        source_object = clicked_image_source(context, event)
        if source_object is None:
            return {"PASS_THROUGH"}
        if is_animated_image(source_object.data):
            self.report(
                {"WARNING"},
                "Rectify only supports a still image",
            )
            return {"CANCELLED"}
        self.source_object_name = source_object.name
        self._source_object = source_object
        self._source_image = source_object.data
        self._source_signature = image_content_signature(source_object.data)
        self._source_matrix = source_object.matrix_world.copy()
        self.quad_json = ""
        self._phase = "POINTS"
        self._preview_texture = None
        self._source_premultiplied = None
        self._points = [(float(event.mouse_region_x), float(event.mouse_region_y))]
        self._cursor = self._points[0]
        self._area_pointer = context.area.as_pointer()
        self._region_pointer = context.region.as_pointer()
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_overlay, (), "WINDOW", "POST_PIXEL"
        )
        self._timer = context.window_manager.event_timer_add(
            0.1, window=context.window
        )
        self._set_point_status(context)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        active_tool = active_view3d_tool_id(context)
        if active_tool is not None and active_tool != RECTIFY_TOOL_ID:
            self._finish(context)
            return {"CANCELLED"}
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            if self._phase == "POINTS" and len(self._points) > 1:
                self._points.pop()
                self._cursor = self._points[-1]
                self._set_point_status(context)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}
            self._finish(context)
            return {"CANCELLED"}
        if event.type == "ESC" and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}
        if (
            self._phase == "ASPECT"
            and event.type in {"LEFT_CTRL", "RIGHT_CTRL"}
            and event.value in {"PRESS", "RELEASE"}
        ):
            self._update_aspect(context, event)
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE":
            if self._phase == "ASPECT":
                self._update_aspect(context, event)
                return {"RUNNING_MODAL"}
            if not drawing_in_region(self._area_pointer, self._region_pointer):
                return {"PASS_THROUGH"}
            self._cursor = (float(event.mouse_region_x), float(event.mouse_region_y))
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if not drawing_in_region(self._area_pointer, self._region_pointer):
                return {"PASS_THROUGH"}
            if self._phase == "ASPECT":
                try:
                    return self.execute(context)
                finally:
                    self._finish(context)
            point = (float(event.mouse_region_x), float(event.mouse_region_y))
            if math.dist(point, self._points[-1]) < 2.0:
                return {"RUNNING_MODAL"}
            self._points.append(point)
            if len(self._points) < 4:
                self._set_point_status(context)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}
            try:
                self._begin_aspect_preview(context, event)
            except (RuntimeError, TypeError, ValueError) as error:
                report_image_edit_exception(self, error)
                self._finish(context)
                return {"CANCELLED"}
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def _begin_aspect_preview(self, context, event):
        import numpy as np

        validated_corner_ring(self._points, MIN_QUAD_AREA)
        source, pixels = read_conversion_source(self)
        image = source.data
        image_size = tuple(image.size)
        quad = screen_path_to_image_pixels(
            self._points, context.region, context.region_data, self._source_matrix,
            image_empty_bounds(source), image_size,
        )
        quad = canonical_perspective_quad(quad)
        if not perspective_quad_overlaps_image(quad, image_size):
            raise ImageEditWarning("Rectify quad does not overlap the source image")

        self._source_premultiplied = _rectify_sampling_pixels(image, pixels)
        del pixels
        preview_size = (PREVIEW_TEXTURE_SIZE, PREVIEW_TEXTURE_SIZE)
        preview = warp_projective_pixels(self._source_premultiplied, quad, preview_size)
        preview = np.asarray(preview).reshape((*preview_size, 4))
        if not np.any(preview[:, :, 3] > 0.0):
            raise ImageEditWarning("Rectify quad contains no visible image pixels")
        self._preview_texture = create_preview_texture(np.flipud(preview))

        self.quad_json = json.dumps(quad.tolist(), separators=(",", ":"))
        self.aspect_ratio = perspective_quad_aspect(quad)
        self._initial_aspect_ratio = self.aspect_ratio
        self._aspect_preset_label = None
        center_x = event.mouse_x - event.mouse_region_x + context.region.width * 0.5
        center_y = event.mouse_y - event.mouse_region_y + context.region.height * 0.5
        context.window.cursor_warp(round(center_x), round(center_y))
        self._aspect_anchor_x = center_x
        self._phase = "ASPECT"
        self._cursor = None
        self._set_aspect_status(context)
        context.area.tag_redraw()

    def execute(self, context):
        try:
            source_object = (
                require_conversion_source(self)
                if self._source_object is not None
                else require_image_empty(self.source_object_name)
            )
            self.source_object_name = source_object.name
            if is_animated_image(source_object.data):
                raise RuntimeError("Rectify only supports a still image")
            quad = validate_perspective_quad(json.loads(self.quad_json))
            if not perspective_quad_overlaps_image(
                quad, tuple(source_object.data.size)
            ):
                self.report(
                    {"WARNING"},
                    "Rectify quad does not overlap the source image",
                )
                return {"CANCELLED"}
            sampling_pixels = self._source_premultiplied
            if sampling_pixels is None:
                sampling_pixels = _rectify_sampling_pixels(source_object.data, image_pixels(source_object.data))
            pixels, output_size, placement_bounds = extract_perspective_pixels(
                sampling_pixels, quad, self.aspect_ratio,
            )
            result_image = create_image_edit_result(
                source_object.data,
                linear_rgba_to_image(source_object.data, pixels.reshape((-1, 4))).ravel(),
                output_size,
            )
            replace_empty_image(
                source_object,
                result_image,
                placement_bounds=placement_bounds,
            )
        except (
            json.JSONDecodeError,
            OverflowError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        finally:
            self._source_premultiplied = None
            self._source_object = None
            self._source_image = None
            self._source_signature = None
        return {"FINISHED"}
