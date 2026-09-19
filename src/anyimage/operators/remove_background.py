import bpy

from ..preferences import configured_background_model
from ..runtime import JobOperatorBase
from ..common.ai import (
    require_input_path,
    report_ai_error,
    invoke_ai_setup_if_needed,
    production_device,
    require_environment,
    require_model,
)

from ..common.image import cleanup_image_input
from ..common.image_target import ImageEditTarget, image_edit_owner
from ..common.hdr_image import HdrBackgroundInput


_HIDDEN = {"HIDDEN", "SKIP_SAVE"}


class RemoveImageBackground(bpy.types.Operator):
    bl_idname = "anyimage.remove_image_background"
    bl_label = "Remove Background"
    bl_description = "Remove the image background with the selected AI model"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        from ..runtime import runtime

        return image_edit_owner(context) is not None and not runtime.server_busy()

    def invoke(self, _context, _event):
        setup_result = invoke_ai_setup_if_needed(self)
        if setup_result is not None:
            return setup_result
        return self.execute(_context)

    def execute(self, _context):
        try:
            result = bpy.ops.anyimage.run_background_removal()
        except RuntimeError as error:
            report_ai_error(self, error)
            return {"CANCELLED"}
        if "CANCELLED" not in result:
            return {"FINISHED"}
        return {"CANCELLED"}


class RunBackgroundRemoval(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.run_background_removal"
    bl_label = "Run Background Removal"
    job_type = "remove-background"
    starting_message = "Starting image background removal"

    input_path: bpy.props.StringProperty(options=_HIDDEN)
    delete_input: bpy.props.BoolProperty(default=False, options=_HIDDEN)

    def execute(self, context):
        self._hdr_input = None
        try:
            self._image_target = ImageEditTarget.capture(context)
            if getattr(self._image_target.image, "is_float", False):
                self._hdr_input = HdrBackgroundInput.prepare(self._image_target.image)
                source_path, self.delete_input = self._hdr_input.path, True
            else:
                source_path, self.delete_input = self._image_target.prepare(context)
        except (OSError, RuntimeError, ValueError, MemoryError) as error:
            self._hdr_input = None
            self._image_target = None
            message = "Not enough memory to prepare the HDR image" if isinstance(error, MemoryError) else str(error)
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.input_path = str(source_path)
        try:
            result = super().execute(context)
        except Exception:
            self.cleanup()
            raise
        if "CANCELLED" in result:
            self.cleanup()
        return result

    def request(self, context):
        require_environment()
        model = configured_background_model(context)
        require_model(model)
        parameters = {
            "input": str(require_input_path(self.input_path)),
            "model": model,
            "device": production_device().lower(),
        }
        if getattr(self, "_hdr_input", None) is not None:
            parameters["output_kind"] = "alpha"
        return parameters

    def response(self, _context, result):
        if getattr(self, "_hdr_input", None) is not None:
            self._hdr_input.apply(self._image_target, result.file("alpha"), prepare_undo=True)
        else:
            self._image_target.apply(result.file("foreground"))
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Remove Background"):
            raise RuntimeError("Unable to create the Remove Background Undo step")
        return "Image background is removed"

    def cleanup(self):
        try:
            cleanup_image_input(self.input_path, self.delete_input)
        finally:
            self._image_target = None
            self._hdr_input = None
