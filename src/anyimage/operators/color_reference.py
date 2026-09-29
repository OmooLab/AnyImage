"""Apply one scene color reference to image targets."""

import time

import bpy
import numpy as np

from ..common.color_match import (
    COLOR_LIMITS,
    LIGHTNESS_LIMITS,
    extract_color_signature,
    match_color_reference,
    resize_rgba_proxy,
)
from ..common.image import (
    create_image_edit_result,
    image_rgba,
    is_color_reference_candidate,
    is_static_image,
)
from ..common.image_target import (
    ImageEditTarget,
    image_edit_owner,
    owner_image,
)
from ..common.viewport import drawing_in_region
from ..common.image_preview import (
    draw_centered_text,
    draw_preview_frame,
    preview_draw_bounds,
    preview_texture_draw_options,
)


def current_color_reference(context):
    """Return the current Scene color reference when it remains valid."""
    settings = getattr(getattr(context, "scene", None), "anyimage_settings", None)
    reference = getattr(settings, "color_reference", None)
    return reference if is_color_reference_candidate(reference) else None


def _context_image(context):
    owner = image_edit_owner(context)
    return None if owner is None else owner_image(owner)


def create_color_preview_image(source_image, rgba):
    """Create one unpacked temporary image for a color-match preview."""
    height, width = rgba.shape[:2]
    image = bpy.data.images.new(
        f"{source_image.name} Color Match Preview",
        width=width,
        height=height,
        alpha=True,
        float_buffer=bool(source_image.is_float),
    )
    try:
        image.colorspace_settings.name = source_image.colorspace_settings.name
        image.alpha_mode = source_image.alpha_mode
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        image.update()
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise
    return image


def update_color_preview_image(image, rgba):
    """Replace the pixels of one standalone color-match preview."""
    if tuple(image.size) != (rgba.shape[1], rgba.shape[0]):
        raise ValueError("The color-match preview dimensions changed")
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    image.update()


class MatchColorReference(bpy.types.Operator):
    bl_idname = "anyimage.match_color_reference"
    bl_label = "Match Color Reference"
    bl_description = "Match this image to the current color reference"
    bl_options = {"UNDO"}

    _MOUSE_SCALE = 0.0025
    _PRECISE_SCALE = 0.2
    _PREVIEW_INTERVAL = 1.0 / 15.0

    @classmethod
    def poll(cls, context):
        reference = current_color_reference(context)
        target = _context_image(context)
        return (
            reference is not None
            and is_static_image(target)
            and target != reference
        )

    def execute(self, context):
        """Apply the default full-resolution match for direct execution."""
        return MatchColorReference._commit(self, context, 0.5, 0.5)

    def invoke(self, context, event):
        """Start an interactive proxy preview."""
        reference = current_color_reference(context)
        self._preview_image = None
        self._handle = None
        self._space_type = None
        try:
            if reference is None:
                raise ValueError("Set a color reference before matching")
            self._target = ImageEditTarget.capture(context)
            if self._target.image == reference:
                raise ValueError("The color reference and target must be different images")
            self._reference_rgba = image_rgba(reference)
            self._reference_image = reference
            self._target_rgba = image_rgba(self._target.image)
            self._reference_proxy = resize_rgba_proxy(self._reference_rgba)
            self._target_proxy = resize_rgba_proxy(self._target_rgba)
            self._reference_signature = extract_color_signature(
                self._reference_rgba,
                alpha_weighted=True,
            )
            self._target_signature = extract_color_signature(
                self._target_rgba,
                alpha_weighted=False,
            )
            self._color = 0.5
            self._lightness = 0.5
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
            preview_rgba = self._preview_pixels()
            self._preview_image = create_color_preview_image(
                self._target.image, preview_rgba
            )
            self._last_preview_time = time.perf_counter()
            self._area = getattr(context, "area", None)
            self._add_preview_handler(context)
            context.window_manager.modal_handler_add(self)
            self._tag_redraw()
            return {"RUNNING_MODAL"}
        except (RuntimeError, TypeError, ValueError) as error:
            self._finish()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

    def modal(self, context, event):
        """Adjust the preview or resolve the transaction."""
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE", "ESC"}:
            self._finish()
            return {"CANCELLED"}
        if event.value == "PRESS" and event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            color = self._color
            lightness = self._lightness
            self._finish()
            return self._commit(context, color, lightness, target=self._target)
        if event.type != "MOUSEMOVE":
            return {"RUNNING_MODAL"}

        scale = self._MOUSE_SCALE * (
            self._PRECISE_SCALE if getattr(event, "shift", False) else 1.0
        )
        self._color = float(
            np.clip(
                self._color + (event.mouse_x - self._mouse_x) * scale,
                *COLOR_LIMITS,
            )
        )
        self._lightness = float(
            np.clip(
                self._lightness + (event.mouse_y - self._mouse_y) * scale,
                *LIGHTNESS_LIMITS,
            )
        )
        self._mouse_x = event.mouse_x
        self._mouse_y = event.mouse_y
        self._tag_redraw()
        now = time.perf_counter()
        if now - self._last_preview_time < self._PREVIEW_INTERVAL:
            return {"RUNNING_MODAL"}
        try:
            update_color_preview_image(
                self._preview_image,
                self._preview_pixels(),
            )
            self._last_preview_time = now
        except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
            self._finish()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def _preview_pixels(self):
        return match_color_reference(
            self._reference_proxy,
            self._target_proxy,
            color=self._color,
            lightness=self._lightness,
            target_float=bool(self._target.image.is_float),
            preview=True,
            reference_signature=self._reference_signature,
            target_signature=self._target_signature,
        )

    def _commit(self, context, color, lightness, *, target=None):
        reference = current_color_reference(context)
        try:
            target = target or ImageEditTarget.capture(context)
            if reference is None:
                raise ValueError("Set a color reference before matching")
            if target is getattr(self, "_target", None) and reference != self._reference_image:
                raise RuntimeError("The color reference changed during preview")
            if target.image == reference:
                raise ValueError("The color reference and target must be different images")
            reference_rgba = (
                self._reference_rgba
                if target is getattr(self, "_target", None)
                else image_rgba(reference)
            )
            target_rgba = (
                self._target_rgba
                if target is getattr(self, "_target", None)
                else image_rgba(target.image)
            )
            matched = match_color_reference(
                reference_rgba,
                target_rgba,
                target_float=bool(target.image.is_float),
                color=color,
                lightness=lightness,
                reference_signature=(
                    self._reference_signature
                    if target is getattr(self, "_target", None)
                    else None
                ),
                target_signature=(
                    self._target_signature
                    if target is getattr(self, "_target", None)
                    else None
                ),
            )
            result = create_image_edit_result(
                target.image,
                np.flipud(matched).ravel(),
                tuple(target.image.size),
            )
            target.commit(result, isolate_shared=True)
        except (RuntimeError, TypeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}

    def _draw_overlay(self):
        if self._preview_image is None or not drawing_in_region(
            self._area_pointer, self._region_pointer
        ):
            return
        import gpu
        from gpu_extras.presets import draw_texture_2d

        region = bpy.context.region
        width, height = self._preview_image.size
        bounds = preview_draw_bounds(
            (region.width, region.height),
            float(width) / float(height),
        )
        left, bottom, draw_width, draw_height = bounds
        texture = gpu.texture.from_image(self._preview_image)
        gpu.state.blend_set("ALPHA")
        try:
            draw_texture_2d(
                texture,
                (left, bottom),
                draw_width,
                draw_height,
                **preview_texture_draw_options(bpy.app.version),
            )
        finally:
            gpu.state.blend_set("NONE")
        draw_preview_frame(bounds)
        center_x = left + draw_width * 0.5
        draw_centered_text(
            f"Color {self._color * 100:.0f}%  ·  Lightness {self._lightness * 100:.0f}%",
            center_x,
            bottom + draw_height * 0.5 - 10.0,
            22,
            (0.25, 0.65, 1.0, 1.0),
        )
        draw_centered_text(
            "Move horizontally: Color  •  vertically: Lightness  •  Shift: Fine",
            center_x,
            bottom - 26.0,
            13,
            (0.85, 0.9, 1.0, 1.0),
        )
        draw_centered_text(
            "LMB or Enter: Confirm  •  RMB or Esc: Cancel",
            center_x,
            bottom - 45.0,
            13,
            (0.85, 0.9, 1.0, 1.0),
        )

    def _add_preview_handler(self, context):
        area = getattr(context, "area", None)
        region = getattr(context, "region", None)
        space_type = type(getattr(context, "space_data", None))
        add_handler = getattr(space_type, "draw_handler_add", None)
        if area is None or region is None or not callable(add_handler):
            return
        self._area_pointer = area.as_pointer()
        self._region_pointer = region.as_pointer()
        self._space_type = space_type
        self._handle = add_handler(
            self._draw_overlay, (), "WINDOW", "POST_PIXEL"
        )

    def _tag_redraw(self):
        area = getattr(self, "_area", None)
        if area is not None and hasattr(area, "tag_redraw"):
            area.tag_redraw()

    def _finish(self):
        if self._handle is not None:
            self._space_type.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        preview_image = self._preview_image
        self._preview_image = None
        if preview_image is not None:
            try:
                bpy.data.images.remove(preview_image, do_unlink=True)
            except ReferenceError:
                pass
        self._tag_redraw()


CLASSES = (MatchColorReference,)
