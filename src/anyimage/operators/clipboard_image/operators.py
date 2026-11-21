import bpy

from .actions import (
    paste_image,
    paste_location,
    replacement_for_context,
    replace_pasted_image,
    target_for_context,
)
from .cache import acquire_packed_image
from .brush import BrushPreviewError
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

        image = None
        image_reused = False
        replacement = None
        paste_succeeded = False
        try:
            replacement = replacement_for_context(context)
            image, image_reused = acquire_packed_image(image_data, suffix)
            if replacement is not None:
                replace_pasted_image(context, replacement, image)
            else:
                paste_image(context, image, self.location if self.properties.is_property_set("location") else None)
            paste_succeeded = True
        except BrushPreviewError as error:
            self.report({"WARNING"}, str(error))
            return {"FINISHED"}
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            self.report({"ERROR"}, bpy.app.translations.pgettext_rpt(
                "Unable to paste clipboard image: {error}"
            ).format(error=bpy.app.translations.pgettext_rpt(str(error))))
            return {"CANCELLED"}
        finally:
            if (image is not None and not image_reused and image.users == 0
                    and (replacement is not None or not paste_succeeded)
                    and (replacement is None or image != replacement.image)):
                bpy.data.images.remove(image)

        name = replacement.image.name if replacement is not None else image.name
        self.report({"INFO"}, bpy.app.translations.pgettext_rpt(
            "Replaced and packed {name}" if replacement is not None else "Pasted and packed {name}"
        ).format(name=name))
        return {"FINISHED"}
