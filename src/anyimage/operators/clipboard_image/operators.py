import bpy

from .actions import (
    BrushPreviewError,
    PasteTargetError,
    acquire_packed_image,
    paste_image,
    paste_location,
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
        if self.paste_target != "PLANE":
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
        try:
            image, image_reused = acquire_packed_image(image_data, suffix)
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
        except BrushPreviewError as error:
            self.report({"WARNING"}, str(error))
            return {"FINISHED"}
        except (OSError, RuntimeError, PasteTargetError) as error:
            if image is not None and not image_reused and image.users == 0:
                bpy.data.images.remove(image)
            self.report({"ERROR"}, f"Unable to paste clipboard image: {error}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Pasted and packed {image.name}")
        return {"FINISHED"}
