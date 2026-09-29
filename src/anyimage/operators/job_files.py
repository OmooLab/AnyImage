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
    bl_description = "Permanently remove unused task outputs and logs, preserving models and the AI environment"

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
            self._preview = connection.client.request(
                "POST", "/job-files/preview", {"protected_paths": protected_image_paths()}, timeout=60,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if not self._preview["jobs"]:
            self.report({"INFO"}, "No unused job files to clear; protected or inaccessible files were kept")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=460, confirm_text="Delete Files")

    def draw(self, _context):
        preview = self._preview
        self.layout.label(text=f"Delete {len(preview['jobs'])} jobs ({preview['bytes'] / 1_000_000:.1f} MB)?")
        self.layout.label(text="This permanently deletes task outputs and task logs.")
        self.layout.label(text="Models, environment and server.log are kept.")
        self.layout.label(text="Close other Blender instances using this Storage Folder.")
        self.layout.label(text="External references and other .blend files cannot be checked.")
        if preview["skipped"] or preview["failed"]:
            self.layout.label(text=f"Kept {preview['skipped'] + len(preview['failed'])} protected or inaccessible jobs.")

    def execute(self, context):
        try:
            if not self.poll(context) or not getattr(self, "_preview", None):
                raise RuntimeError("Preview and confirm cleanup while the server is idle")
            connection = runtime.server.connection
            if connection is None or connection.instance_id != self._instance:
                raise RuntimeError("Job Server changed; preview cleanup again")
            result = connection.client.request("POST", "/job-files/clear", {
                "jobs": self._preview["jobs"], "protected_paths": protected_image_paths(),
            }, timeout=60)
        except (OSError, RuntimeError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        kept = result["skipped"] + len(result["failed"])
        self.report({"WARNING"} if kept else {"INFO"},
                    f"Deleted {len(result['jobs'])} jobs ({result['bytes'] / 1_000_000:.1f} MB); kept {kept}")
        return {"FINISHED"}
