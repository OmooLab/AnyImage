import bpy

from .operators.ai_setup import ClearModels, SetupAIEnvironment
from .operators.job_files import ClearJobFiles
from .properties import (
    COLOR_REFERENCE_PALETTE_PROPERTIES,
    COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES,
)
from .runtime import runtime


from .server.model_catalog import DOWNLOADABLE_MODELS


class ColorMatchPanel(bpy.types.Panel):
    bl_label = "Color Match"
    bl_idname = "ANYIMAGE_PT_color_match"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AnyImage"
    bl_order = 10

    def draw(self, context):
        settings = context.scene.anyimage_settings
        self.layout.template_icon_view(
            settings,
            "color_reference_choice",
            show_labels=False,
            scale=6.0,
            scale_popup=5.0,
        )
        row = self.layout.row(align=True)
        palette_count = min(
            settings.color_reference_palette_count,
            len(COLOR_REFERENCE_PALETTE_PROPERTIES),
        )
        count = palette_count or 1
        display_weights = [
            max(getattr(settings, COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES[index]), 0.0) ** 0.5
            if palette_count else 1.0
            for index in range(count)
        ]
        display_total = sum(display_weights) or 1.0
        for index in range(count):
            cell = row.row(align=True)
            cell.scale_x = max(display_weights[index] / display_total * count, 0.1)
            cell.prop(settings, COLOR_REFERENCE_PALETTE_PROPERTIES[index], text="")

class ServerPanel(bpy.types.Panel):
    bl_label = "Job Server"
    bl_idname = "ANYIMAGE_PT_server"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AnyImage"
    bl_order = 0

    def draw(self, _context):
        layout = self.layout
        busy = runtime.server_busy()
        if not runtime.environment_ready():
            layout.label(
                text="Environment is not installed",
                icon="ERROR",
            )
            layout.operator("anyimage.open_server_log", icon="TEXT")
            setup_row = layout.row()
            setup_row.enabled = not busy
            setup_row.operator(
                SetupAIEnvironment.bl_idname,
                text="Set Up AI Server…",
                icon="IMPORT",
            )
            return

        status = runtime.server_status()
        state = status.get("state", "STOPPED")
        server_running = state in {"READY", "BUSY"}
        icons = {
            "READY": "RADIOBUT_ON",
            "BUSY": "TIME",
            "STARTING": "TIME",
            "ERROR": "ERROR",
            "UNAVAILABLE": "ERROR",
            "STOPPED": "PAUSE",
        }
        row = layout.row(align=True)
        if server_running:
            row.label(
                text=(
                    "Running"
                    if state == "READY"
                    else "Running (Busy)"
                ),
                icon=icons[state],
            )
            controls = row.row(align=True)
            controls.operator(
                "anyimage.restart_server",
                text="",
                icon="FILE_REFRESH",
            )
            controls.operator(
                "anyimage.stop_server",
                text="",
                icon="PAUSE",
            )
        elif state == "STOPPED":
            row.operator(
                "anyimage.start_server",
                text="Start",
                icon="PLAY",
            )
        else:
            row.label(
                text=status.get("message", state.title()),
                icon=icons.get(state, "QUESTION"),
            )
            if state == "ERROR":
                row.operator(
                    "anyimage.start_server",
                    text="Start",
                    icon="PLAY",
                )

        layout.operator("anyimage.open_server_log", icon="TEXT")

        cached = (
            status.get("resources", {})
            .get("model_manager", {})
            .get("loaded", {})
        )
        slots = tuple(
            (cached.get(family), task)
            for family, task in (
                ("geometry", "Generate Depth Map"),
                ("background", "Remove Background"),
                ("upscale", "Upscale Image"),
            )
        )
        has_loaded_models = any(name for name, _task in slots)
        cached_row = layout.row(align=True)
        cached_row.label(text="Models Loaded")
        if has_loaded_models:
            clear = cached_row.row(align=True)
            clear.enabled = state == "READY"
            clear.operator(
                ClearModels.bl_idname,
                text="Unload",
                icon="TRASH",
            )
        cached_list = layout.column(align=True)
        for name, task in slots:
            slot = cached_list.row(align=True)
            model = DOWNLOADABLE_MODELS.get(name)
            tier = model.tier if model is not None else None
            slot.label(
                text=f"{task}  [ {tier} ]" if tier else task,
                icon="RADIOBUT_ON" if name else "RADIOBUT_OFF",
            )


class DangerZonePanel(bpy.types.Panel):
    bl_label = "Danger Zone"
    bl_idname = "ANYIMAGE_PT_danger_zone"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AnyImage"
    bl_order = 100
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, _context):
        row = self.layout.row()
        row.operator_context = "INVOKE_DEFAULT"
        row.enabled = ClearJobFiles.poll(None)
        row.operator(ClearJobFiles.bl_idname, icon="TRASH")
