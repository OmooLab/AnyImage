"""Add generated Cutout shapes and normals to the shared pie menu."""

from ...ai_properties import ai_ready
from . import interaction
from .ai_shape import CUTOUT_SHAPE_LABELS, DEPTH_CUTOUT_SHAPES
from .operators import SelectCutoutSelection as SharedSelection

CUTOUT_SHAPE_BUTTONS = (
    *interaction.CUTOUT_SHAPE_BUTTONS,
    ("DEPTH_SYMMETRY", "META_BALL"),
    ("DEPTH_SOLID", "SURFACE_NCURVE"),
)


def open_shape_pie(context, event, source_object, selection_path, *, gesture="LASSO"):
    ready = ai_ready()
    generate_normal = ready and bool(context.scene.anyimage_settings.cutout_generate_normal)

    def create_button(pie, shape, label, icon):
        if not generate_normal and shape not in DEPTH_CUTOUT_SHAPES:
            return interaction.create_shape_button(pie, shape, label, icon)
        from .ai_operators import CutoutSelectionToShape

        operator = pie.operator(CutoutSelectionToShape.bl_idname, text=label, icon=icon)
        operator.generate_normal = generate_normal
        return operator

    interaction.open_shape_pie(
        context,
        event,
        source_object,
        selection_path,
        gesture=gesture,
        buttons=CUTOUT_SHAPE_BUTTONS if ready else interaction.CUTOUT_SHAPE_BUTTONS,
        labels=CUTOUT_SHAPE_LABELS,
        create_button=create_button,
    )


class SelectCutoutSelection(SharedSelection):
    bl_idname = "anyimage.select_cutout_selection"
    bl_label = "Start Cutout Selection"

    show_shape_menu = staticmethod(open_shape_pie)
