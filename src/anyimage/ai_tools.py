from .tools import CutoutTool as SharedCutoutTool
from .common.ai import draw_ai_property, draw_ai_setup


class CutoutTool(SharedCutoutTool):
    def draw_settings(context, layout, tool):
        SharedCutoutTool.draw_settings(context, layout, tool)
        status = draw_ai_setup(layout)
        draw_ai_property(layout, context.scene.anyimage_settings, "cutout_generate_normal", status)
