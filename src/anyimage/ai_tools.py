from .tools import CutoutTool as SharedCutoutTool
from .common.ai import draw_ai_setup


class CutoutTool(SharedCutoutTool):
    def draw_settings(context, layout, tool):
        SharedCutoutTool.draw_settings(context, layout, tool)
        status = draw_ai_setup(layout)
        row = layout.row()
        row.enabled = status["ready"]
        row.prop(context.scene.anyimage_settings, "cutout_generate_normal")
