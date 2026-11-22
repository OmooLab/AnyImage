import bpy

from .actions import (
    paste_image,
    paste_location,
    replacement_for_context,
    replace_pasted_image,
    target_for_context,
)
from .cache import clipboard_source
from ...common.viewport import redraw_area
from .brush import active_brush, set_brush_preview
from .clipboard import (
    ClipboardImageError,
    ClipboardImageUnavailable,
    clipboard_image_supported,
    read_clipboard_image,
)


class PasteClipboardImage(bpy.types.Operator):
    bl_idname = "anyimage.paste_clipboard_image"
    bl_label = "Paste Clipboard Image"
    bl_description = "Paste and pack the clipboard image for the current editor"
    bl_options = {"REGISTER", "UNDO"}

    location: bpy.props.FloatVectorProperty(
        size=3,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    @classmethod
    def poll(cls, context):
        if not clipboard_image_supported():
            return False
        return target_for_context(context) is not None

    def invoke(self, context, event):
        location = paste_location(context, event)
        if location is not None:
            values = tuple(location)
            self.location = (*values, 0.0)[:3]
        return self.execute(context)

    def execute(self, context):
        try:
            image_data, suffix = read_clipboard_image()
        except ClipboardImageUnavailable:
            return {"PASS_THROUGH"}
        except ClipboardImageError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        try:
            replacement = replacement_for_context(context)
            with clipboard_source(image_data, suffix) as image:
                if replacement is not None:
                    pasted = replace_pasted_image(replacement, image)
                else:
                    location = self.location if self.properties.is_property_set("location") else None
                    pasted = paste_image(context, image, location)
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            self.report({"ERROR"}, bpy.app.translations.pgettext_rpt(
                "Unable to paste clipboard image: {error}"
            ).format(error=bpy.app.translations.pgettext_rpt(str(error))))
            return {"CANCELLED"}

        redraw_area(context)
        if getattr(context, "mode", None) == "PAINT_TEXTURE" and target_for_context(context) == "TOOL_TEXTURE":
            try:
                set_brush_preview(context, active_brush(context), pasted)
            except (RuntimeError, OSError, ValueError) as error:
                self.report({"WARNING"}, str(error))
                return {"FINISHED"}

        self.report({"INFO"}, bpy.app.translations.pgettext_rpt(
            "Replaced and packed {name}" if replacement is not None else "Pasted and packed {name}"
        ).format(name=pasted.name))
        return {"FINISHED"}
