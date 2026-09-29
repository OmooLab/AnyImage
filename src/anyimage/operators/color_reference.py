"""Set and apply one scene color reference."""

import time
from dataclasses import dataclass

import bpy
import numpy as np

from ..common.color_match import (
    CONTRAST_LIMITS,
    MATCH_LIMITS,
    match_color_reference,
    resize_rgba_proxy,
)
from ..common.image import create_image_edit_result, image_rgba, is_animated_image
from ..common.image_target import (
    ImageEditTarget,
    image_edit_owner,
    material_has_other_object_user,
    owner_image,
)


def valid_color_reference(image):
    """Return whether an Image can provide static color pixels."""
    try:
        width, height = (int(value) for value in image.size)
        return (
            image is not None
            and width > 0
            and height > 0
            and not is_animated_image(image)
        )
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


def current_color_reference(context):
    """Return the current Scene color reference when it remains valid."""
    settings = getattr(getattr(context, "scene", None), "anyimage_settings", None)
    reference = getattr(settings, "color_reference", None)
    return reference if valid_color_reference(reference) else None


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


@dataclass
class ColorMatchPreview:
    """Own and restore a temporary image binding for one captured target."""

    target: ImageEditTarget
    image: object
    owner: object
    copied_material: object = None

    @classmethod
    def bind(cls, target, preview_image):
        """Bind a preview image without changing the source image pixels."""
        target.validate()
        if target.tree is None:
            target.owner.data = preview_image
            return cls(target, preview_image, target.owner)
        if (
            target.object_owner is not None
            and material_has_other_object_user(target.material, target.object_owner)
        ):
            copied_material = target.material.copy()
            try:
                target.object_owner.material_slots[target.material_slot].material = copied_material
                copied_node = next(
                    (
                        node
                        for node in copied_material.node_tree.nodes
                        if node.get("anyimage_identity") == target.node_identity
                    ),
                    None,
                )
                if copied_node is None or copied_node.image != target.image:
                    raise RuntimeError("Unable to isolate the color-match preview")
                copied_node.image = preview_image
                return cls(target, preview_image, copied_node, copied_material)
            except Exception:
                target.object_owner.material_slots[target.material_slot].material = target.material
                if copied_material.users == 0:
                    bpy.data.materials.remove(copied_material)
                raise
        target.owner.image = preview_image
        return cls(target, preview_image, target.owner)

    def update(self, rgba):
        """Replace preview pixels without packing the temporary image."""
        if tuple(self.image.size) != (rgba.shape[1], rgba.shape[0]):
            raise ValueError("The color-match preview dimensions changed")
        self.image.pixels.foreach_set(np.flipud(rgba).ravel())
        self.image.update()

    def restore(self):
        """Restore bindings still owned by this preview and release resources."""
        restored = False
        try:
            if self.copied_material is not None:
                slot = self.target.object_owner.material_slots[self.target.material_slot]
                if slot.material == self.copied_material and self.owner.image == self.image:
                    slot.material = self.target.material
                    restored = True
            elif self.target.tree is None:
                if self.owner.data == self.image:
                    self.owner.data = self.target.image
                    restored = True
            elif self.owner.image == self.image:
                self.owner.image = self.target.image
                restored = True
        except (AttributeError, ReferenceError, RuntimeError):
            restored = False
        finally:
            if self.copied_material is not None and self.copied_material.users == 0:
                bpy.data.materials.remove(self.copied_material)
            if self.image.users == 0:
                bpy.data.images.remove(self.image)
        return restored


class SetColorReference(bpy.types.Operator):
    bl_idname = "anyimage.set_color_reference"
    bl_label = "Set Color Reference"
    bl_description = "Use this image as the color reference for later matches"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return valid_color_reference(_context_image(context))

    def execute(self, context):
        image = _context_image(context)
        if not valid_color_reference(image):
            self.report({"ERROR"}, "Select a static image to use as the color reference")
            return {"CANCELLED"}
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
            and valid_color_reference(target)
            and target != reference
        )

    def execute(self, context):
        """Apply the default full-resolution match for direct execution."""
        return MatchColorReference._commit(self, context, 1.0, 0.0)

    def invoke(self, context, event):
        """Start an interactive proxy preview."""
        reference = current_color_reference(context)
        self._preview = None
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
            self._match = 1.0
            self._contrast = 0.0
            self._mouse_x = event.mouse_x
            self._mouse_y = event.mouse_y
            preview_rgba = self._preview_pixels()
            preview_image = create_color_preview_image(self._target.image, preview_rgba)
            try:
                self._preview = ColorMatchPreview.bind(self._target, preview_image)
            except Exception:
                if preview_image.users == 0:
                    bpy.data.images.remove(preview_image)
                raise
            self._last_preview_time = time.perf_counter()
            self._area = getattr(context, "area", None)
            self._update_header()
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        except (RuntimeError, TypeError, ValueError) as error:
            self._restore_preview()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

    def modal(self, context, event):
        """Adjust the preview or resolve the transaction."""
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE", "ESC"}:
            self._restore_preview()
            return {"CANCELLED"}
        if event.value == "PRESS" and event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            match = self._match
            contrast = self._contrast
            if not self._restore_preview():
                self.report({"ERROR"}, "The color-match target changed during preview")
                return {"CANCELLED"}
            return self._commit(context, match, contrast, target=self._target)
        if event.type != "MOUSEMOVE":
            return {"RUNNING_MODAL"}

        scale = self._MOUSE_SCALE * (
            self._PRECISE_SCALE if getattr(event, "shift", False) else 1.0
        )
        self._match = float(
            np.clip(
                self._match + (event.mouse_x - self._mouse_x) * scale,
                *MATCH_LIMITS,
            )
        )
        self._contrast = float(
            np.clip(
                self._contrast + (event.mouse_y - self._mouse_y) * scale,
                *CONTRAST_LIMITS,
            )
        )
        self._mouse_x = event.mouse_x
        self._mouse_y = event.mouse_y
        self._update_header()
        now = time.perf_counter()
        if now - self._last_preview_time < self._PREVIEW_INTERVAL:
            return {"RUNNING_MODAL"}
        try:
            self._preview.update(self._preview_pixels())
            self._last_preview_time = now
        except (ReferenceError, RuntimeError, TypeError, ValueError) as error:
            self._restore_preview()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def _preview_pixels(self):
        return match_color_reference(
            self._reference_proxy,
            self._target_proxy,
            match=self._match,
            contrast=self._contrast,
            target_float=bool(self._target.image.is_float),
            preview=True,
        )

    def _commit(self, context, match, contrast, *, target=None):
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
                match=match,
                contrast=contrast,
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

    def _update_header(self):
        if self._area is not None and hasattr(self._area, "header_text_set"):
            self._area.header_text_set(
                f"Match {self._match * 100:.0f}% · Contrast {self._contrast * 100:+.0f}%"
            )

    def _restore_preview(self):
        area = getattr(self, "_area", None)
        if area is not None and hasattr(area, "header_text_set"):
            area.header_text_set(None)
        preview = getattr(self, "_preview", None)
        if preview is None:
            return False
        self._preview = None
        return preview.restore()


CLASSES = (SetColorReference, MatchColorReference)
