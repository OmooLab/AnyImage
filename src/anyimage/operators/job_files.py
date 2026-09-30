"""Confirm deletion of unused server job artifacts."""

from pathlib import Path

import bpy

from ..common.image import image_is_packed
from ..runtime import runtime


def protected_image_paths():
    """Protect whole jobs containing an unpacked image, including tiled images."""
    return [str(Path(bpy.path.abspath(image.filepath, library=image.library)).resolve())
            for image in bpy.data.images if image.filepath and not image_is_packed(image)]


class ClearJobFiles(bpy.types.Operator):
    bl_idname = "anyimage.clear_job_files"
    bl_label = "Clear Job Files"
    bl_description = "Delete unused job outputs and logs"

    @classmethod
    def poll(cls, _context):
        return (runtime.environment_ready() and not runtime.server_busy()
                and runtime.server_status().get("state") in {"READY", "STOPPED"})

    def invoke(self, context, _event):
        try:
            if not self.poll(context):
                raise RuntimeError("Wait for the current task to finish")
            connection = runtime.server.ensure()
            self._instance = connection.instance_id
            self._preview = connection.client.preview_job_files(protected_image_paths())
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if not self._preview["jobs"]:
            self.report({"INFO"}, "No unused job files to clear")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=460, confirm_text="Delete Files")

    def draw(self, _context):
        preview = self._preview
        self.layout.label(text=f"Delete {len(preview['jobs'])} jobs ({preview['bytes'] / 1_000_000:.1f} MB)?")
        self.layout.label(text="Permanently delete job outputs and logs.")
        self.layout.label(text="Files used by other projects may be deleted.")
        if preview["skipped"] or preview["failed"]:
            self.layout.label(text=f"Kept {preview['skipped'] + len(preview['failed'])} jobs skipped.")

    def execute(self, context):
        try:
            if not self.poll(context) or not getattr(self, "_preview", None):
                raise RuntimeError("Preview and confirm cleanup while the server is idle")
            connection = runtime.server.connection
            if connection is None or connection.instance_id != self._instance:
                raise RuntimeError("Job Server changed; preview cleanup again")
            result = connection.client.clear_job_files(self._preview["jobs"], protected_image_paths())
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        kept = result["skipped"] + len(result["failed"])
        self.report({"WARNING"} if kept else {"INFO"},
                    f"Deleted {len(result['jobs'])} jobs ({result['bytes'] / 1_000_000:.1f} MB); kept {kept}")
        return {"FINISHED"}
