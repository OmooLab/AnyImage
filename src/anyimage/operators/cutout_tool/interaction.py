"""Cutout Selection validation and Shape-menu interaction helpers."""

from ...properties import ai_ready
from .shape import CUTOUT_SHAPE_LABELS

CUTOUT_SHAPE_BUTTONS = (
    ("FLAT", "MESH_GRID"),
    ("SOLID", "MESH_UVSPHERE"),
    ("DEPTH_SYMMETRY", "META_BALL"),
    ("DEPTH_SOLID", "SURFACE_NCURVE"),
)
CUTOUT_SHAPE_OPERATOR_ID = "anyimage.cutout_selection_to_shape"


def _pie_button(
    pie,
    shape,
    label,
    icon,
    source_name,
    selection_path_json,
    generate_normal,
    edge_length,
    alpha_threshold,
    fine_outline,
    gesture,
):
    operator = pie.operator(
        CUTOUT_SHAPE_OPERATOR_ID,
        text=label,
        icon=icon,
    )
    operator.source_object_name = source_name
    operator.selection_path_json = selection_path_json
    operator.shape = shape
    operator.generate_normal = generate_normal
    operator.edge_length = edge_length
    operator.alpha_threshold = alpha_threshold
    operator.fine_outline = fine_outline
    operator.gesture = gesture


def open_shape_pie(
    context,
    event,
    source_object,
    selection_path,
    *,
    gesture="LASSO",
):
    source_name = source_object.name
    selection_path_json = selection_path.to_json()
    settings = context.scene.anyimage_settings
    edge_length = settings.cutout_edge_length
    ready = ai_ready()
    generate_normal = ready and bool(
        getattr(settings, "cutout_generate_normal", False)
    )
    alpha_threshold = settings.cutout_alpha_threshold
    fine_outline = settings.cutout_fine_outline

    def draw(menu, _context):
        pie = menu.layout.menu_pie()
        buttons = CUTOUT_SHAPE_BUTTONS if ready else CUTOUT_SHAPE_BUTTONS[:2]
        for shape, icon in buttons:
            _pie_button(
                pie,
                shape,
                CUTOUT_SHAPE_LABELS[shape],
                icon,
                source_name,
                selection_path_json,
                generate_normal,
                edge_length,
                alpha_threshold,
                fine_outline,
                gesture,
            )

    context.window_manager.popup_menu_pie(
        event,
        draw,
        title="Cutout Shape",
        icon="MESH_DATA",
    )
