import bpy

from .runtime import runtime

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
            setup_row = layout.row()
            setup_row.enabled = not busy
            setup_row.operator(
                "anyimage.setup_ai_environment",
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

        if server_running:
            cached = (
                status.get("resources", {})
                .get("model_manager", {})
                .get("loaded", {})
            )
            cached_names = [name for name in cached.values() if name]
            cached_row = layout.row(align=True)
            if len(cached_names) > 1:
                cached_list = cached_row.column(align=True)
                cached_list.label(text="Loaded Models:")
                for name in cached_names:
                    cached_list.label(text=name)
            else:
                cached_row.label(
                    text=(
                        f"Loaded Models: {cached_names[0]}"
                        if cached_names
                        else "No Models Loaded"
                    )
                )
            clear = cached_row.row(align=True)
            clear.enabled = state == "READY"
            clear.operator(
                "anyimage.clear_models",
                text="",
                icon="TRASH",
            )
