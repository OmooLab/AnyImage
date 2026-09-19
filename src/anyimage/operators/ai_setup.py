import bpy

from ..preferences import ADDON_PACKAGE
from ..runtime import JobOperatorBase, runtime
from ..server.model_catalog import DEFAULT_MODEL_KEYS
from ..properties import (
    ai_status,
    model_download_size,
    model_record,
)
from ..common.ai import report_ai_error, require_environment


def format_download_size(size):
    return f"{size / 1_000_000:.0f} MB"


class SetupAIEnvironment(bpy.types.Operator):
    bl_idname = "anyimage.setup_ai_environment"
    bl_label = "Set Up AI Server"
    bl_description = "Install the environment and required AI models"

    use_mirror: bpy.props.BoolProperty(
        name="Use China Mirror",
        description="Download Python and packages from China mirrors",
        default=False,
    )

    @classmethod
    def poll(cls, _context):
        return not runtime.server_busy()

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(
            self, width=440, title="Set Up AI", confirm_text="Install"
        )

    def draw(self, _context):
        layout = self.layout
        status = ai_status()
        if not status["environment_ready"]:
            required_size = sum(
                model_download_size(model_key) for model_key in DEFAULT_MODEL_KEYS
            )
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

        if status["ready"]:
            layout.label(text="AI Server is ready.", icon="CHECKMARK")
            return

        labels = []
        for model_key in status["missing_models"]:
            model = model_record(model_key)
            labels.append(model["label"] if model else model_key)
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

    def execute(self, _context):
        status = ai_status()
        if status["ready"]:
            return {"FINISHED"}
        try:
            if status["environment_ready"]:
                return bpy.ops.anyimage.download_required_models("INVOKE_DEFAULT")
            installer = (
                bpy.ops.anyimage.install_environment_mirror
                if self.use_mirror
                else bpy.ops.anyimage.install_environment
            )
            return installer("INVOKE_DEFAULT")
        except RuntimeError as error:
            report_ai_error(self, error)
            return {"CANCELLED"}


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


class ClearModels(bpy.types.Operator):
    bl_idname = "anyimage.clear_models"
    bl_label = "Unload Models"
    bl_description = "Unload AI models to free memory. Downloaded model files are kept."

    def execute(self, _context):
        try:
            runtime.clear_resource("model_manager")
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}
