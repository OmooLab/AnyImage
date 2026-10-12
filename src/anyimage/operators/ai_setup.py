import bpy

from ..preferences import ADDON_PACKAGE, storage_root
from ..runtime import JobOperatorBase, runtime
from ..server.model_catalog import DEFAULT_MODEL_KEYS, get_downloadable_model
from ..properties import (
    model_download_size,
    model_record,
)
from ..common.ai import require_environment
from ..common.server_location import inspect_installation, server_root


def format_download_size(size):
    return f"{size / 1_000_000:.0f} MB"


class SetupAIServer(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.setup_ai_server"
    bl_label = "Set Up AI Server"
    bl_description = "Install the environment and required AI models"
    job_type = "setup-server"
    starting_message = "Preparing AI Server"

    location: bpy.props.StringProperty(
        name="Server Location",
        description="Choose .anyimage, a folder inside it, or a parent folder for a new installation",
        subtype="DIR_PATH", options={"SKIP_SAVE"},
    )

    use_mirror: bpy.props.BoolProperty(
        name="Use China Mirror",
        description="Download Python and packages from China mirrors",
        default=False,
    )

    @classmethod
    def poll(cls, _context):
        return not runtime.server_busy()

    def invoke(self, context, _event):
        self._location_preview = None
        self.location = str(storage_root().parent)
        return context.window_manager.invoke_props_dialog(
            self, width=520, title="Set Up AI Server", confirm_text="Continue"
        )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "location")
        preview = getattr(self, "_location_preview", None)
        if preview is None or preview[0] != self.location:
            try:
                target = server_root(self.location)
                preview = (self.location, target, inspect_installation(target), "")
            except (OSError, ValueError) as error:
                preview = (self.location, None, None, str(error))
            self._location_preview = preview
        _, target, status, error = preview
        if error:
            layout.label(text=error, icon="ERROR")
            return
        layout.label(text=str(target), icon="FILE_FOLDER")
        if not status["environment_ready"]:
            required_size = sum(model_download_size(key) for key in status["missing_models"])
            layout.label(
                text="Set up AI features for depth, background removal and upscaling."
            )
            layout.label(
                text=(
                    "Downloads the runtime and required models "
                    f"({format_download_size(required_size)} for models)."
                )
            )
            layout.separator(type="LINE")
            layout.prop(self, "use_mirror")
            return

        if not status["missing_models"]:
            layout.label(text="Use existing AI Server installation.", icon="CHECKMARK")
            return

        labels = [get_downloadable_model(key).label for key in status["missing_models"]]
        missing_size = sum(
            model_download_size(model_key)
            for model_key in status["missing_models"]
        )
        layout.label(
            text="AI environment installed.",
            icon="CHECKMARK",
        )
        layout.label(text=f"Download: {', '.join(labels)}")
        layout.label(
            text=f"{format_download_size(missing_size)} · Usually 2–10 minutes."
        )

    def controller(self, runtime):
        target = server_root(self.location)
        return runtime.setup_controller(target, mirror=self.use_mirror, online=bpy.app.online_access)


class MigrateAIServer(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.migrate_ai_server"
    bl_label = "Migrate AI Server"
    bl_description = "Migrate the complete .anyimage folder to another location"
    job_type = "migrate-server"
    starting_message = "Migrating AI Server"

    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"SKIP_SAVE"})
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    @classmethod
    def poll(cls, _context):
        return not runtime.server_busy()

    def invoke(self, context, _event):
        if runtime.pending_migration():
            return self.execute(context)
        self.directory = str(storage_root().parent)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def controller(self, runtime):
        target = None if runtime.pending_migration() else server_root(self.directory)
        return runtime.migrate_controller(target)


class OpenAIEnvironmentSettings(bpy.types.Operator):
    bl_idname = "anyimage.open_ai_environment_settings"
    bl_label = "Settings"
    bl_description = "Open the AnyImage add-on preferences"

    def execute(self, context):
        result = bpy.ops.screen.userpref_show("INVOKE_DEFAULT", section="ADDONS")
        if "FINISHED" not in result:
            return {"CANCELLED"}
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "PREFERENCES":
                    continue
                with context.temp_override(window=window, area=area):
                    bpy.ops.preferences.addon_show(module=ADDON_PACKAGE)
                return {"FINISHED"}
        return {"FINISHED"}


class DownloadModel(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.download_model"
    bl_label = "Download Model"
    job_type = "download-model"

    model: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def request(self, _context):
        require_environment()
        if not bpy.app.online_access:
            raise RuntimeError("Online Access is disabled in Blender Preferences")
        model = model_record(self.model)
        label = model["label"] if model else self.model
        self.starting_message = f"Starting {label} download"
        return {"model": self.model}


class DownloadRequiredModels(JobOperatorBase, bpy.types.Operator):
    bl_idname = "anyimage.download_required_models"
    bl_label = "Download Required Models"
    job_type = "download-required-models"
    starting_message = "Starting required model downloads"

    def request(self, _context):
        require_environment()
        if not bpy.app.online_access:
            raise RuntimeError("Online Access is disabled in Blender Preferences")
        return {"models": list(DEFAULT_MODEL_KEYS)}


class UnloadModels(bpy.types.Operator):
    bl_idname = "anyimage.unload_models"
    bl_label = "Unload Models"
    bl_description = "Free memory used by AI models to keep viewport and rendering responsive"

    @classmethod
    def poll(cls, _context):
        return not runtime.maintenance_busy() and runtime.server_status().get("state") == "READY"

    def execute(self, _context):
        try:
            runtime.clear_resource("model_manager")
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    SetupAIServer, MigrateAIServer, OpenAIEnvironmentSettings,
    DownloadModel, DownloadRequiredModels, UnloadModels,
)
