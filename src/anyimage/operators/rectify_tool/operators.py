"""Rectify interaction and Blender image replacement."""

import json
import math

import bpy

from ...common.viewport import (
    active_view3d_tool_id,
    deserialize_matrix,
    draw_dashed_line,
    draw_polygon_fill,
    drawing_in_region,
    image_edit_poll,
    report_image_edit_exception,
    resolve_image_edit_click,
    screen_path_to_image_pixels,
    serialize_matrix,
)
from ...common.image import (
    create_image_edit_result,
    image_pixels,
    image_empty_bounds,
    replace_empty_image,
    require_image_empty,
    is_animated_image,
    warp_projective_pixels,
)
from .geometry import (
    MAX_INTERACTIVE_ASPECT,
    MIN_INTERACTIVE_ASPECT,
    canonical_perspective_quad,
    extract_perspective_pixels,
    perspective_quad_aspect,
    perspective_quad_overlaps_image,
    validate_perspective_quad,
)
from .preview import (
    PREVIEW_TEXTURE_SIZE,
    aspect_ratio_from_mouse,
    create_perspective_preview_image,
    draw_aspect_hud,
    draw_preview_frame,
    interactive_preview_polygon,
    preview_draw_bounds,
    preview_texture_draw_options,
    snapped_aspect_ratio,
)


MIN_QUAD_AREA = 16.0
RECTIFY_TOOL_ID = "anyimage.rectify"


class RectifyImagePerspective(bpy.types.Operator):
    bl_idname = "anyimage.rectify_image_perspective"
    bl_label = "Rectify Image Perspective"
    bl_description = "Select four corners of an image area to correct its perspective into a rectangle."
    bl_options = {"REGISTER", "UNDO"}

    source_object_name: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    source_matrix_data: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
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
    _preview_image = None
    _source_pixels = None
    _initial_aspect_ratio = 1.0
    _raw_aspect_ratio = 1.0
    _aspect_preset_label = None
    _aspect_anchor_x = 0.0
    _area_pointer = 0
    _region_pointer = 0

    @classmethod
    def poll(cls, context):
        return image_edit_poll(context)

    def _draw_preview(self):
        if self._preview_image is None:
            return
        import gpu
        from gpu_extras.presets import draw_texture_2d

        region = bpy.context.region
        left, bottom, width, height = preview_draw_bounds(
            (region.width, region.height), self.aspect_ratio
        )
        bounds = (left, bottom, width, height)
        texture = gpu.texture.from_image(self._preview_image)
        gpu.state.blend_set("ALPHA")
        try:
            draw_texture_2d(
                texture,
                (left, bottom),
                width,
                height,
                **preview_texture_draw_options(bpy.app.version),
            )
        finally:
            gpu.state.blend_set("NONE")
        draw_preview_frame(bounds)
        draw_aspect_hud(
            bounds, self.aspect_ratio, self._aspect_preset_label
        )

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
        remaining = 4 - len(self._points)
        context.workspace.status_text_set(
            f"Rectify: click {remaining} more corner"
            f"{'s' if remaining != 1 else ''}; click order does not matter; "
            "Backspace removes, RMB or Esc cancels"
        )

    def _set_aspect_status(self, context):
        context.workspace.status_text_set(
            f"Rectify Aspect {self.aspect_ratio:.3f}: "
            "move mouse horizontally, LMB confirms, Backspace returns, "
            "RMB or Esc cancels"
        )

    def _update_aspect(self, context, event):
        self._raw_aspect_ratio = aspect_ratio_from_mouse(
            self._initial_aspect_ratio,
            float(event.mouse_x) - self._aspect_anchor_x,
        )
        if event.ctrl:
            self.aspect_ratio, self._aspect_preset_label = snapped_aspect_ratio(
                self._raw_aspect_ratio
            )
        else:
            self.aspect_ratio = self._raw_aspect_ratio
            self._aspect_preset_label = None
        self._set_aspect_status(context)
        context.area.tag_redraw()

    def _remove_preview(self):
        preview_image = self._preview_image
        self._preview_image = None
        if preview_image is None:
            return
        try:
            bpy.data.images.remove(preview_image, do_unlink=True)
        except ReferenceError:
            pass

    def _finish(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        self._remove_preview()
        context.workspace.status_text_set(None)
        if context.area is not None:
            context.area.tag_redraw()

    def cancel(self, context):
        self._finish(context)

    def invoke(self, context, event):
        source_object, should_edit = resolve_image_edit_click(
            context, event, self.report
        )
        if not should_edit:
            return {"FINISHED"} if source_object is not None else {"CANCELLED"}
        if source_object is None:
            return {"CANCELLED"}
        if is_animated_image(source_object.data):
            self.report(
                {"WARNING"},
                "Rectify only supports a still image",
            )
            return {"CANCELLED"}
        self.source_object_name = source_object.name
        self.source_matrix_data = serialize_matrix(source_object.matrix_world)
        self.quad_json = ""
        self._phase = "POINTS"
        self._preview_image = None
        self._source_pixels = None
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
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}
        if event.type == "BACK_SPACE" and event.value == "PRESS":
            if self._phase == "ASPECT":
                self._remove_preview()
                self._source_pixels = None
                self._phase = "POINTS"
                self._points.pop()
                self._cursor = self._points[-1]
                self._set_point_status(context)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}
            if len(self._points) > 1:
                self._points.pop()
                self._set_point_status(context)
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}
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
                self._finish(context)
                return self.execute(context)
            point = (float(event.mouse_region_x), float(event.mouse_region_y))
            if math.dist(point, self._points[-1]) < 2.0:
                return {"RUNNING_MODAL"}
            self._points.append(point)
            if len(self._points) < 4:
                self._set_point_status(context)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}
            try:
                source_object = require_image_empty(self.source_object_name)
            except RuntimeError as error:
                self.report({"ERROR"}, str(error))
                self._finish(context)
                return {"CANCELLED"}
            try:
                canonical_perspective_quad(self._points, MIN_QUAD_AREA)
                matrix_world = deserialize_matrix(self.source_matrix_data)
                quad = screen_path_to_image_pixels(
                    self._points,
                    context.region,
                    context.region_data,
                    matrix_world,
                    image_empty_bounds(source_object),
                    tuple(source_object.data.size),
                )
                quad = canonical_perspective_quad(quad)
                if not perspective_quad_overlaps_image(
                    quad, tuple(source_object.data.size)
                ):
                    self.report(
                        {"WARNING"},
                        "Rectify quad does not overlap the source image",
                    )
                    self._finish(context)
                    return {"CANCELLED"}
                self.quad_json = json.dumps(
                    quad.tolist(), separators=(",", ":")
                )
                self.aspect_ratio = perspective_quad_aspect(quad)
                self._initial_aspect_ratio = self.aspect_ratio
                self._raw_aspect_ratio = self.aspect_ratio
                self._aspect_preset_label = None
                center_x = (
                    float(event.mouse_x)
                    - float(event.mouse_region_x)
                    + context.region.width * 0.5
                )
                center_y = (
                    float(event.mouse_y)
                    - float(event.mouse_region_y)
                    + context.region.height * 0.5
                )
                context.window.cursor_warp(round(center_x), round(center_y))
                self._aspect_anchor_x = center_x
                import numpy as np

                self._source_pixels = image_pixels(source_object.data)
                preview_pixels = warp_projective_pixels(
                    self._source_pixels,
                    tuple(source_object.data.size),
                    quad,
                    (PREVIEW_TEXTURE_SIZE, PREVIEW_TEXTURE_SIZE),
                )
                if not np.any(
                    np.asarray(preview_pixels).reshape((-1, 4))[:, 3] > 0.0
                ):
                    self.report(
                        {"WARNING"},
                        "Rectify quad contains no visible image pixels",
                    )
                    self._finish(context)
                    return {"CANCELLED"}
                self._preview_image = create_perspective_preview_image(
                    source_object.data, preview_pixels
                )
                self._phase = "ASPECT"
                self._cursor = None
            except (RuntimeError, TypeError, ValueError) as error:
                report_image_edit_exception(self, error)
                self._finish(context)
                return {"CANCELLED"}
            self._set_aspect_status(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def execute(self, context):
        try:
            source_object = require_image_empty(self.source_object_name)
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        try:
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
            source_pixels = self._source_pixels
            if source_pixels is None or len(source_pixels) != len(
                source_object.data.pixels
            ):
                source_pixels = image_pixels(source_object.data)
            pixels, output_size, placement_bounds = extract_perspective_pixels(
                source_pixels,
                tuple(source_object.data.size),
                quad,
                self.aspect_ratio,
            )
            result_image = create_image_edit_result(
                source_object.data,
                pixels,
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
        return {"FINISHED"}
