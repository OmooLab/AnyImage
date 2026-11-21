"""Add generated Cutout shapes and normals to the shared pie menu."""

from ...common.ai import ai_ready
from . import interaction
from .ai_operators import CutoutSelectionToShape
from .operators import CreateCutoutShape, SelectCutoutSelection as SharedSelection


def open_shape_pie(context, event, source_object, selection_path, *, gesture="LASSO"):
    buttons = None
    if ai_ready():
        basic = CutoutSelectionToShape if context.scene.anyimage_settings.cutout_generate_normal else CreateCutoutShape
        buttons = (
            *interaction.flat_and_solid_buttons(basic),
            ("DEPTH_SYMMETRY", "META_BALL", CutoutSelectionToShape),
            ("DEPTH_SOLID", "SURFACE_NCURVE", CutoutSelectionToShape),
        )
    interaction.open_shape_pie(
        context,
        event,
        source_object,
        selection_path,
        gesture=gesture,
        buttons=buttons,
    )


class SelectCutoutSelection(SharedSelection):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"

    show_shape_menu = staticmethod(open_shape_pie)
