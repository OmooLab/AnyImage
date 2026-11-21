"""Shared Cutout pie layout and captured selection parameters."""

from .shape import CUTOUT_SHAPE_LABELS


def flat_and_solid_buttons(operator):
    return (("FLAT", "MESH_GRID", operator), ("SOLID", "MESH_UVSPHERE", operator))


def open_shape_pie(
    context,
    event,
    source_object,
    selection_path,
    *,
    gesture="LASSO",
    buttons=None,
):
    if buttons is None:
        from .operators import CreateCutoutShape

        buttons = flat_and_solid_buttons(CreateCutoutShape)
    settings = context.scene.anyimage_settings
    parameters = {
        "source_object_name": source_object.name,
        "selection_path_json": selection_path.to_json(),
        "edge_length": settings.cutout_edge_length,
        "alpha_threshold": settings.cutout_alpha_threshold,
        "fine_outline": settings.cutout_fine_outline,
        "gesture": gesture,
    }

    def draw(menu, _context):
        pie = menu.layout.menu_pie()
        for shape, icon, operator_type in buttons:
            operator = pie.operator(
                operator_type.bl_idname, text=CUTOUT_SHAPE_LABELS[shape], text_ctxt="AnyImage", icon=icon,
            )
            operator.shape = shape
            for name, value in parameters.items():
                setattr(operator, name, value)

    context.window_manager.popup_menu_pie(
        event,
        draw,
        title="Cutout Shape",
        icon="MESH_DATA",
    )
