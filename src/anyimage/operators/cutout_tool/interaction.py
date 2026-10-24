"""Shared Cutout pie layout and captured selection parameters."""

from .shape import CUTOUT_SHAPE_LABELS

CUTOUT_SHAPE_BUTTONS = (("FLAT", "MESH_GRID"), ("SOLID", "MESH_UVSPHERE"))


def create_shape_button(pie, shape, label, icon):
    from .operators import CreateCutoutShape

    return pie.operator(CreateCutoutShape.bl_idname, text=label, icon=icon)


def open_shape_pie(
    context,
    event,
    source_object,
    selection_path,
    *,
    gesture="LASSO",
    buttons=CUTOUT_SHAPE_BUTTONS,
    labels=CUTOUT_SHAPE_LABELS,
    create_button=create_shape_button,
):
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
        for shape, icon in buttons:
            operator = create_button(pie, shape, labels[shape], icon)
            operator.shape = shape
            for name, value in parameters.items():
                setattr(operator, name, value)

    context.window_manager.popup_menu_pie(
        event,
        draw,
        title="Cutout Shape",
        icon="MESH_DATA",
    )
