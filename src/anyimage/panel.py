import bpy

from .operators.ai_setup import UnloadModels, SetupAIServer
from .runtime import runtime


from .server.model_catalog import DOWNLOADABLE_MODELS


class ServerPanel(bpy.types.Panel):
    bl_label = "AI Server"
    bl_idname = "ANYIMAGE_PT_server"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AnyImage"
    bl_order = 0

    def draw(self, _context):
        layout = self.layout
        runtime.draw_server_controls(layout, setup_operator=SetupAIServer.bl_idname)
        runtime.draw_jobs(layout)
        if not runtime.is_ready():
            return

        cached = runtime.resource("model_manager").get("loaded", {})
        slots = tuple(
            (cached.get(family), job)
            for family, job in (
                ("geometry", "Depth & Normal Model"),
                ("background", "Remove Background"),
                ("upscale", "Upscale Image"),
            )
        )
        has_loaded_models = any(name for name, _job in slots)
        cached_row = layout.row(align=True)
        cached_row.label(text="Models Loaded")
        if has_loaded_models:
            clear = cached_row.row(align=True)
            clear.enabled = (runtime.state() == "IDLE")
            clear.operator(
                UnloadModels.bl_idname,
                text="Unload",
                icon="TRASH",
            )
        cached_list = layout.column(align=True)
        for name, job in slots:
            slot = cached_list.row(align=True)
            model = DOWNLOADABLE_MODELS.get(name)
            tier = model.tier if model is not None else None
            slot.label(
                text=bpy.app.translations.pgettext_iface("{job}  [ {tier} ]").format(
                    job=bpy.app.translations.pgettext_iface(job), tier=tier,
                ) if tier else bpy.app.translations.pgettext_iface(job),
                translate=False,
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
        row.operator("anyimage.clear_job_files", icon="TRASH")
