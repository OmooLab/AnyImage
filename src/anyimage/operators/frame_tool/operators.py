"""Frame interaction, source preparation, and Blender image replacement."""

import bpy

from ...common.image import (
    create_image_edit_result,
    image_empty_bounds,
    image_pixels,
    is_image_empty,
    premultiplied_rgba,
    replace_empty_image,
    is_animated_image,
)
from ...preferences import configured_max_frame_resolution
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


def _frame_source(source_object, region, view3d, view_matrix, *, active):
    import numpy as np

    image_size = tuple(source_object.data.size)
    pixels = image_pixels(source_object.data)
    width, height = image_size
    bounds = image_empty_bounds(source_object)
    source = frame_source_projection(
        view3d.perspective_matrix,
        view_matrix,
        source_object.matrix_world,
        bounds,
        (region.width, region.height),
        perspective=view3d.is_perspective,
    )
    source.update(
        {
            "active": bool(active),
            "image_size": image_size,
            "name": source_object.name,
            "object": source_object,
            "pixels": premultiplied_rgba(pixels, image_size),
            "rgba": np.flipud(pixels.reshape((height, width, 4))),
        }
    )
    return source


def selected_frame_sources(context):
    """Return selected still Image Empties with the active object last."""
    active = active_image_edit_source(context)
    sources = [
        source for source in context.selected_objects if is_image_empty(source)
    ]
    for source in sources:
        if is_animated_image(source.data):
            raise ValueError("Frame only supports still images")
    return tuple(
        sorted(sources, key=lambda source: (source is active, source.name))
    )


def apply_frame(context, source_objects, frame_quad):
    """Bake selected projections into the active Image Empty."""
    active = context.active_object
    if active not in source_objects:
        raise ValueError("The active Image Empty is not a Frame source")
    view3d = context.region_data
    sources = tuple(
        _frame_source(
            source,
            context.region,
            view3d,
            view3d.view_matrix,
            active=source is active,
        )
        for source in source_objects
    )
    active_source = next(source for source in sources if source["active"])
    active_overlap = frame_source_overlap(active_source, frame_quad)
    if not active_overlap:
        raise ImageEditWarning("Frame does not overlap the active Image Empty")
    output_size = frame_output_size(
        frame_quad,
        (context.region.width, context.region.height),
        configured_max_frame_resolution(context),
    )
    pixels = composite_frame_pixels(sources, frame_quad, output_size)
    depth_location = frame_depth_location(active_source, active_overlap)
    matrix, display_size = frame_result_transform(
        frame_quad,
        depth_location,
        context.region,
        view3d,
        output_size,
    )
    result_image = create_image_edit_result(active.data, pixels, output_size)
    old_matrix = active.matrix_world.copy()
    old_display_size = active.empty_display_size
    old_offset = tuple(active.empty_image_offset)
    source_images = []
    for source in source_objects:
        if all(image is not source.data for image in source_images):
            source_images.append(source.data)
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
        if source is not active:
            bpy.data.objects.remove(source, do_unlink=True)
    for image in source_images:
        try:
            if image.users == 0 and not image.use_fake_user:
                bpy.data.images.remove(image, do_unlink=True)
        except (ReferenceError, RuntimeError):
            pass
    return active


class FrameImages(bpy.types.Operator):
    bl_idname = "anyimage.frame_images"
    bl_label = "Frame Images"
    bl_description = "Draw a rectangle to combine selected images into one image from the current view."
    bl_options = {"UNDO"}

    _active_name = ""
    _source_names = ()
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
            sources = selected_frame_sources(context)
        except (TypeError, ValueError) as error:
            report_image_edit_exception(self, error)
            return {"CANCELLED"}
        self._active_name = context.active_object.name
        self._source_names = tuple(source.name for source in sources)
        point = (float(event.mouse_region_x), float(event.mouse_region_y))
        self._start = point
        self._cursor = point
        self._area_pointer = context.area.as_pointer()
        self._region_pointer = context.region.as_pointer()
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_overlay, (), "WINDOW", "POST_PIXEL"
        )
        context.workspace.status_text_set(
            "Frame: drag a rectangle to merge selected Image Empties; "
            "RMB or Esc cancels"
        )
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
                active = bpy.data.objects.get(self._active_name)
                sources = tuple(
                    bpy.data.objects.get(name) for name in self._source_names
                )
                if (
                    not is_image_empty(active)
                    or any(not is_image_empty(source) for source in sources)
                    or context.active_object is not active
                ):
                    raise ValueError("The selected Image Empties changed during Frame")
                apply_frame(context, sources, frame)
            except (RuntimeError, TypeError, ValueError) as error:
                report_image_edit_exception(self, error)
                self._finish(context)
                return {"CANCELLED"}
            self._finish(context)
            return {"FINISHED"}
        return {"PASS_THROUGH"}
