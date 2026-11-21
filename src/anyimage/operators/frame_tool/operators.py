"""Frame interaction, source preparation, and Blender image replacement."""

import bpy

from ...common.image import (
    create_image_edit_result,
    image_empty_bounds,
    image_pixels,
    is_animated_image,
    is_image_empty,
    replace_empty_image,
)
from ...common.projective_image import premultiplied_rgba
from ...common.color_space import image_rgba_to_linear, linear_rgba_to_image
from ...preferences import configured_max_frame_resolution
from ...common.tool_status import set_tool_status
from ...common.viewport import (
    active_image_edit_source,
    active_view3d_tool_id,
    draw_dashed_line,
    draw_polygon_fill,
    drawing_in_region,
    image_edit_poll,
    rectangle_screen_path,
    report_image_edit_exception,
)
from ...common.selection import ImageEditWarning
from .projection import (
    frame_depth_location,
    frame_output_size,
    frame_result_transform,
    frame_source_overlap,
    frame_source_projection,
)
from .compositing import composite_frame_pixels


FRAME_TOOL_ID = "anyimage.frame"


def _project_frame_object(source_object, view3d, region_size):
    return frame_source_projection(
        view3d.perspective_matrix,
        view3d.view_matrix,
        source_object.matrix_world,
        image_empty_bounds(source_object),
        region_size,
        perspective=view3d.is_perspective,
    )


def selected_frame_sources(context):
    """Return selected still Image Empties with the active object last."""
    active = active_image_edit_source(context)
    sources = [
        source for source in context.selected_objects if is_image_empty(source)
    ]
    for source in sources:
        if is_animated_image(source.data):
            raise ValueError("Frame only supports still images")
    sources.remove(active)
    sources.append(active)
    return tuple(sources)


def apply_frame(context, source_objects, frame_quad):
    """Bake selected projections into the active Image Empty."""
    import numpy as np

    active = context.active_object
    if active not in source_objects:
        raise ValueError("The active Image Empty is not a Frame source")
    view3d = context.region_data
    region_size = (context.region.width, context.region.height)
    active_source = _project_frame_object(active, view3d, region_size)
    active_overlap = frame_source_overlap(active_source, frame_quad)
    if not active_overlap:
        raise ImageEditWarning("Frame does not overlap the active Image Empty")
    output_size = frame_output_size(
        frame_quad,
        region_size,
        configured_max_frame_resolution(context),
    )
    sources = []
    buffers = {}
    for obj in source_objects:
        is_active = obj == active
        source = active_source if is_active else _project_frame_object(obj, view3d, region_size)
        image = obj.data
        if image not in buffers:
            width, height = image.size
            pixels = image_rgba_to_linear(image, image_pixels(image).reshape((-1, 4)))
            buffers[image] = {
                "image_size": (width, height),
                "rgba": np.flipud(pixels.reshape((height, width, 4))),
            }
            if len(source_objects) > 1:
                buffers[image]["pixels"] = premultiplied_rgba(pixels, (width, height))
        source.update(buffers[image], active=is_active, object=obj, name=obj.name)
        sources.append(source)
    pixels = composite_frame_pixels(sources, frame_quad, output_size)
    depth_location = frame_depth_location(active_source, active_overlap)
    matrix, display_size = frame_result_transform(
        frame_quad,
        depth_location,
        context.region,
        view3d,
        output_size,
    )
    result_image = create_image_edit_result(
        active.data,
        linear_rgba_to_image(active.data, pixels.reshape((-1, 4))).ravel(),
        output_size,
    )
    old_matrix = active.matrix_world.copy()
    old_display_size = active.empty_display_size
    old_offset = tuple(active.empty_image_offset)
    try:
        active.matrix_world = matrix
        active.empty_display_size = display_size
        active.empty_image_offset = (-0.5, -0.5)
        replace_empty_image(
            active, result_image,
            removed_objects=tuple(source for source in source_objects if source != active),
        )
    except Exception:
        active.matrix_world = old_matrix
        active.empty_display_size = old_display_size
        active.empty_image_offset = old_offset
        raise
    for source in source_objects:
        if source != active:
            bpy.data.objects.remove(source, do_unlink=True)
    return active


class FrameImages(bpy.types.Operator):
    bl_idname = "anyimage.frame_images"
    bl_label = "Frame Images"
    bl_description = "Draw a rectangle to combine selected images into one image from the current view."
    bl_options = {"UNDO"}

    _sources = ()
    _start = None
    _cursor = None
    _handle = None
    _area_pointer = 0
    _region_pointer = 0

    @classmethod
    def poll(cls, context):
        return image_edit_poll(context)

    def _draw_overlay(self):
        if not drawing_in_region(self._area_pointer, self._region_pointer):
            return
        frame = rectangle_screen_path(self._start, self._cursor)
        if not frame:
            return
        draw_polygon_fill(frame)
        draw_dashed_line((*frame, frame[0]))

    def _finish(self, context):
        self._sources = ()
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        context.workspace.status_text_set(None)
        if context.area is not None:
            context.area.tag_redraw()

    def cancel(self, context):
        self._finish(context)

    def invoke(self, context, event):
        try:
            self._sources = selected_frame_sources(context)
        except (TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        point = (float(event.mouse_region_x), float(event.mouse_region_y))
        self._start = point
        self._cursor = point
        self._area_pointer = context.area.as_pointer()
        self._region_pointer = context.region.as_pointer()
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_overlay, (), "WINDOW", "POST_PIXEL"
        )
        set_tool_status(context, ("Draw Frame", "DRAG"))
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        active_tool = active_view3d_tool_id(context)
        if active_tool is not None and active_tool != FRAME_TOOL_ID:
            self._finish(context)
            return {"CANCELLED"}
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._finish(context)
            return {"CANCELLED"}
        if event.type == "MOUSEMOVE":
            self._cursor = (
                float(event.mouse_region_x),
                float(event.mouse_region_y),
            )
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self._cursor = (
                float(event.mouse_region_x),
                float(event.mouse_region_y),
            )
            frame = rectangle_screen_path(self._start, self._cursor)
            if not frame:
                self._finish(context)
                return {"CANCELLED"}
            try:
                current = selected_frame_sources(context)
                if current[-1] != self._sources[-1] or set(current) != set(self._sources):
                    raise ValueError("The selected Image Empties changed during Frame")
                apply_frame(context, self._sources, frame)
            except ReferenceError:
                self.report({"ERROR"}, "The selected Image Empties changed during Frame")
                return {"CANCELLED"}
            except (RuntimeError, TypeError, ValueError) as error:
                report_image_edit_exception(self, error)
                return {"CANCELLED"}
            finally:
                self._finish(context)
            return {"FINISHED"}
        return {"PASS_THROUGH"}
