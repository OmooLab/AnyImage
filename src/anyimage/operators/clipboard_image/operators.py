import bpy

from .actions import (
    BrushPreviewError,
    acquire_packed_image,
    paste_image,
    paste_location,
    replacement_for_context,
    replace_pasted_image,
    target_for_context,
)
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

    import_as: bpy.props.EnumProperty(
        name="Import As",
        translation_context="AnyImage",
        description="Choose the 3D View representation for the image",
        items=(
            (
                "PLANE",
                "Plane",
                "Create a mesh plane with an image material",
            ),
            (
                "REFERENCE",
                "Reference Image",
                "Create an image Empty like dragging an image into Blender",
            ),
        ),
        default="REFERENCE",
    )
    shadeless: bpy.props.BoolProperty(
        name="Shadeless",
        description=(
            "Use an Emission shader so the image is unaffected by scene lighting"
        ),
        default=False,
    )
    paste_target: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )
    location: bpy.props.FloatVectorProperty(
        size=3,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    location_set: bpy.props.BoolProperty(
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    is_replacement: bpy.props.BoolProperty(
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        if not clipboard_image_supported():
            return False
        return target_for_context(context) is not None

    def execute(self, context):
        return self._paste(context)

    def invoke(self, context, event):
        self.paste_target = target_for_context(context) or ""
        location = paste_location(context, event)
        if location is not None:
            values = tuple(location)
            self.location = (*values, 0.0)[:3]
            self.location_set = True
        return self._paste(context, event)

    def draw(self, _context):
        if self.is_replacement or self.paste_target != "PLANE":
            return
        self.layout.prop(self, "import_as")
        if self.import_as == "PLANE":
            self.layout.prop(self, "shadeless")

    def _paste(self, context, event=None):
        if not self.paste_target:
            self.paste_target = target_for_context(context) or ""

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
            self.is_replacement = replacement is not None
            image, image_reused = acquire_packed_image(image_data, suffix)
            if replacement is not None:
                replace_pasted_image(context, replacement, image)
            else:
                location = None
                if self.location_set:
                    location = self.location
                    if self.paste_target == "NODE":
                        location = location[:2]
                paste_image(
                    context,
                    image,
                    event,
                    location=location,
                    import_as=self.import_as,
                    shadeless=self.shadeless,
                )
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
