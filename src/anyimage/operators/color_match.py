"""Apply one scene color reference to image targets."""

import time

import bpy
import numpy as np

from ..common.color_match import (
    COLOR_LIMITS,
    LIGHTNESS_LIMITS,
    apply_color_match,
    build_color_match,
    resize_rgba_proxy,
)
from ..common.color_reference import get_color_reference, is_color_reference_candidate
from ..common.color_space import image_rgba_to_linear, linear_rgba_to_image
from ..common.image import (
    TEMPORARY_IMAGE_PREVIEW_PROPERTY,
    COLOR_REFERENCE_PROPERTY,
    create_image_edit_result,
    owner_image,
    image_rgba,
    is_static_image,
)
from ..common.image_target import (
    ImageEditTarget,
    material_has_other_object_user,
    image_edit_owner,
)
from ..common.tool_status import draw_tool_status
from ..common.viewport import drawing_in_region
from ..common.image_preview import draw_preview_caption


def _live_datablock(block):
    """Return None when Blender has removed a preview datablock."""
    try:
        return block if block is not None and block.as_pointer() else None
    except ReferenceError:
        return None


def draw_match_status(header, _context):
    draw_tool_status(
        header.layout,
        ("Confirm", "LEFTMOUSE"),
        ("Cancel", "RIGHTMOUSE"),
        ("Fine Adjustment", "LEFT_SHIFT"),
    )


def current_color_reference(context):
    """Return the current Scene color reference when it remains valid."""
    settings = getattr(getattr(context, "scene", None), "anyimage_settings", None)
    reference = getattr(settings, "color_reference", None)
    return reference if is_color_reference_candidate(reference) else None


def _context_image(context):
    return owner_image(image_edit_owner(context))


class SetColorReference(bpy.types.Operator):
    bl_idname = "anyimage.set_color_reference"
    bl_label = "Set Color Reference"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return is_static_image(_context_image(context))

    def execute(self, context):
        image = _context_image(context)
        image[COLOR_REFERENCE_PROPERTY] = True
        context.scene.anyimage_settings.color_reference = image
        return {"FINISHED"}


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
        return MatchColorReference._commit(self, context, 0.5, 0.0)

    def invoke(self, context, event):
        """Start an interactive proxy preview."""
        reference = current_color_reference(context)
        self._preview_image = None
        space = context.space_data
        self._preview_world = space.id if getattr(space, "shader_type", None) == "WORLD" else None
        self._preview_material = None
        self._preview_owner = None
        self._handle = None
        self._space_type = None
        self._status_workspace = None
        self._timer = None
        self._window_manager = context.window_manager
        try:
            if reference is None:
                raise ValueError("Set a color reference before matching")
            self._target, pixels = ImageEditTarget.capture_with_pixels(context)
            if self._target.image == reference:
                raise ValueError("The color reference and target must be different images")
            prepared = get_color_reference(reference, refresh=True)
            self._reference = prepared
            self._preview_signature = self._target.content_signature
            target_rgba = image_rgba(self._target.image, pixels)
            self._preview_match = build_color_match(
                prepared.transfer,
                resize_rgba_proxy(image_rgba_to_linear(self._target.image, target_rgba)),
                target_float=bool(self._target.image.is_float),
            )
            self._color = 0.5
            self._lightness = 0.0
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
            self._update_preview()
            self._last_preview_time = time.perf_counter()
            self._preview_dirty = False
            self._area = getattr(context, "area", None)
            self._add_preview_handler(context)
            self._timer = context.window_manager.event_timer_add(
                self._PREVIEW_INTERVAL, window=context.window,
            )
            context.window_manager.modal_handler_add(self)
            context.workspace.status_text_set(draw_match_status)
            self._status_workspace = context.workspace
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
            try:
                self._restore_preview()
                return self._commit(context, self._color, self._lightness, target=self._target)
            finally:
                self._finish()
        if event.type not in {"MOUSEMOVE", "TIMER"}:
            return {"RUNNING_MODAL"}
        if event.type == "MOUSEMOVE":
            scale = self._MOUSE_SCALE * (
                self._PRECISE_SCALE if getattr(event, "shift", False) else 1.0
            )
            color = float(np.clip(
                self._color + (event.mouse_x - self._mouse_x) * scale, *COLOR_LIMITS,
            ))
            lightness = float(np.clip(
                self._lightness + (event.mouse_y - self._mouse_y) * scale, *LIGHTNESS_LIMITS,
            ))
            self._preview_dirty |= color != self._color or lightness != self._lightness
            self._color = color
            self._lightness = lightness
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
        now = time.perf_counter()
        if self._preview_dirty and now - self._last_preview_time >= self._PREVIEW_INTERVAL:
            try:
                self._update_preview()
            except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
                self._finish()
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}
            self._last_preview_time = now
            self._preview_dirty = False
        elif event.type == "TIMER":
            return {"RUNNING_MODAL"}
        self._tag_redraw()
        return {"RUNNING_MODAL"}

    def _update_preview(self):
        target = self._target
        matched = apply_color_match(
            self._preview_match, color=self._color, lightness=self._lightness,
        )
        rgba = linear_rgba_to_image(target.image, matched)
        pixels = np.flipud(rgba).ravel()
        if self._preview_image is not None:
            self._preview_image.pixels.foreach_set(pixels)
            self._preview_image.update()
            if self._preview_world is not None:
                self._preview_image.update_tag()
                self._preview_world.update_tag()
            return
        self._preview_image = create_image_edit_result(target.image, pixels, rgba.shape[1::-1], pack=False)
        self._preview_image[TEMPORARY_IMAGE_PREVIEW_PROPERTY] = True
        owner = target.owner
        if target.object_owner is not None and material_has_other_object_user(target.material, target.object_owner):
            self._preview_material = target.material.copy()
            owner = self._preview_material.node_tree.nodes[owner.name]
            slot = target.object_owner.material_slots[target.material_slot]
            self._original_slot_link = slot.link
            slot.link = "OBJECT"
            slot.material = self._preview_material
        self._preview_owner = owner
        if target.tree is None:
            owner.data = self._preview_image
        else:
            owner.image = self._preview_image
        if self._preview_world is not None:
            self._preview_world.update_tag()

    def _restore_preview(self):
        if self._preview_image is None:
            return
        target = self._target
        image = _live_datablock(self._preview_image)
        material = _live_datablock(self._preview_material)
        try:
            if self._preview_material is not None:
                slots = target.object_owner.material_slots
                if target.material_slot < len(slots) and slots[target.material_slot].material == material:
                    slot = slots[target.material_slot]
                    slot.material = target.material
                    slot.link = self._original_slot_link
            elif self._preview_owner is not None and owner_image(self._preview_owner) == image:
                if target.tree is None:
                    self._preview_owner.data = target.image
                else:
                    self._preview_owner.image = target.image
        except ReferenceError:
            pass
        finally:
            if material is not None and not material.users:
                bpy.data.materials.remove(material)
            if image is not None:
                bpy.data.images.remove(image)
            self._preview_material = self._preview_owner = self._preview_image = None
            if _live_datablock(self._preview_world) is not None:
                self._preview_world.update_tag()

    def cancel(self, context):
        self._finish()

    def _commit(self, context, color, lightness, *, target=None):
        reference = current_color_reference(context)
        try:
            interactive = target is not None
            pixels = None
            if target is None:
                target, pixels = ImageEditTarget.capture_with_pixels(context)
            if reference is None:
                raise ValueError("Set a color reference before matching")
            if interactive and reference != self._reference.image:
                raise RuntimeError("The color reference changed during preview")
            if target.image == reference:
                raise ValueError("The color reference and target must be different images")
            prepared = get_color_reference(reference, refresh=True)
            if interactive:
                if target.content_signature != self._preview_signature:
                    raise RuntimeError("The source image content or settings have changed")
                if (prepared.content_digest != self._reference.content_digest
                        or prepared.metadata != self._reference.metadata):
                    raise RuntimeError("The color reference changed during preview")
            if color == 0.0 and lightness == 0.0:
                target.validate()
                return {"FINISHED"}
            matched = apply_color_match(
                build_color_match(
                    prepared.transfer, image_rgba_to_linear(target.image, image_rgba(target.image, pixels)),
                    target_float=bool(target.image.is_float),
                    prepared_match=self._preview_match if interactive else None,
                ),
                color=color,
                lightness=lightness,
            )
            result = create_image_edit_result(
                target.image,
                np.flipud(linear_rgba_to_image(target.image, matched)).ravel(),
                tuple(target.image.size),
            )
            target.commit(result)
        except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}

    def _draw_overlay(self):
        if self._preview_image is None or not drawing_in_region(
            self._area_pointer, self._region_pointer
        ):
            return
        draw_preview_caption(
            bpy.context.region,
            bpy.app.translations.pgettext_iface(
                "Color {color:.0f}% | Lightness {lightness:.0f}%"
            ).format(color=self._color * 100, lightness=self._lightness * 100),
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
        if self._preview_world is not None:
            for window in self._window_manager.windows:
                for viewport in window.screen.areas:
                    if viewport.type == "VIEW_3D":
                        viewport.tag_redraw()

    def _finish(self):
        if self._status_workspace is not None:
            self._status_workspace.status_text_set(None)
            self._status_workspace = None
        self._restore_preview()
        self._preview_match = None
        self._reference = None
        self._target = None
        if self._timer is not None:
            self._window_manager.event_timer_remove(self._timer)
            self._timer = None
        if self._handle is not None:
            self._space_type.draw_handler_remove(self._handle, "WINDOW")
            self._handle = None
        self._preview_signature = None
        self._tag_redraw()
