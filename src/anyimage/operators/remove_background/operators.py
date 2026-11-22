import bpy

from ...ai_preferences import configured_background_model
from ...runtime import JobOperator
from ...common.ai import invoke_ai_setup_if_needed, model_job_parameters
from ...common.image_input import cleanup_image_input
from ...common.image_target import ImageEditTarget, editable_still_image
from .image import BackgroundInput


class RemoveImageBackground(JobOperator, bpy.types.Operator):
    bl_idname = "anyimage.remove_image_background"
    bl_label = "Remove Background"
    bl_description = "Remove the image background with the selected AI model"
    bl_options = {"REGISTER"}
    job_type = "remove_background"
    starting_message = "Starting image background removal"

    _background_input = None

    @classmethod
    def poll(cls, context):
        from ...runtime import runtime

        return editable_still_image(context) is not None and runtime.can_submit()

    def invoke(self, context, _event):
        setup_result = invoke_ai_setup_if_needed(self)
        if setup_result is not None:
            return setup_result
        return self.execute(context)

    def request(self, context):
        parameters = model_job_parameters(configured_background_model(context))
        try:
            self._image_target, rgba = ImageEditTarget.capture(context)
            self._background_input = BackgroundInput.prepare(self._image_target.image, rgba)
        except MemoryError as error:
            raise RuntimeError("Not enough memory to prepare the image") from error
        return {**parameters, "input": str(self._background_input.path)}

    def response(self, _context, result):
        self._background_input.apply(self._image_target, result.file("alpha"), prepare_undo=True)
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Remove Background"):
            raise RuntimeError("Unable to create the Remove Background Undo step")
        return "Image background is removed"

    def cleanup(self):
        try:
            if self._background_input is not None:
                cleanup_image_input(self._background_input.path)
        finally:
            self._image_target = None
            self._background_input = None
