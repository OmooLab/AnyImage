import bpy
from ...common.selection import ImageEditWarning
from .geometry import CUTOUT_ALPHA_THRESHOLD, build_base_shape, effective_cutout_edge_length


def _cutout_content_values(
    source_alpha, selection_values=None, *, alpha_threshold=CUTOUT_ALPHA_THRESHOLD
):
    """Combine local image Alpha with optional pure Selection geometry."""
    import numpy as np

    alpha = np.asarray(source_alpha, dtype=np.float32)
    if alpha.ndim != 2:
        raise ValueError("The Cutout source Alpha must be two-dimensional")
    if selection_values is None:
        values = alpha.copy()
    else:
        selection = np.asarray(selection_values, dtype=np.float32)
        if alpha.shape != selection.shape:
            raise ValueError("The Cutout source Alpha does not match the Selection")
        values = alpha * selection
    if not np.any((values > 0.0) & (values >= alpha_threshold)):
        raise ImageEditWarning("The Cutout selection contains no visible image pixels")
    return values


def build_cutout_shape(
    context,
    source_object,
    edge_length,
    content_values,
    content_bounds,
    alpha_threshold,
    fine_outline,
    report,
):
    effective_length = effective_cutout_edge_length(
        context, source_object, edge_length, content_values, content_bounds, alpha_threshold
    )
    if report is not None and effective_length > edge_length * (1 + 1e-6):
        units = context.scene.unit_settings
        label = bpy.utils.units.to_string(
            units.system if units.system != "NONE" else "METRIC",
            "LENGTH",
            effective_length * units.scale_length,
            precision=4,
        )
        report(
            {"INFO"},
            bpy.app.translations.pgettext_rpt("Effective Edge Length: {length}").format(
                length=label
            ),
        )
    base_shape = build_base_shape(
        context,
        source_object,
        effective_length,
        content_values,
        content_bounds,
        alpha_threshold=alpha_threshold,
        fine_outline=fine_outline,
    )
    return base_shape


def push_cutout_undo(shape):
    message = f"Convert to {shape.replace('_', ' ').title()}"
    if "FINISHED" not in bpy.ops.ed.undo_push(message=message):
        raise RuntimeError(f"Unable to create the {message} Undo step")
