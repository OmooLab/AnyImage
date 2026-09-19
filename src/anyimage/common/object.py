"""Shared Blender Object and Geometry Nodes Modifier helpers."""

import bpy


def blender_frame_rotation():
    """Map Image Empty local axes to the canonical Blender object frame."""
    from mathutils import Matrix

    return Matrix(
        (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def modifier_input_identifier(node_group, name, *, subtype=None):
    for item in node_group.interface.items_tree:
        if item.item_type != "SOCKET" or item.in_out != "INPUT":
            continue
        if item.name == name and (subtype is None or getattr(item, "subtype", None) == subtype):
            return item.identifier
    raise RuntimeError(f"Geometry Nodes input is missing: {name}")


def _modifier_input_slots(modifier):
    """Return the runtime input collection, or None for the legacy API."""
    properties = getattr(modifier, "properties", None)
    if properties is None:
        return None
    return getattr(properties, "inputs", None)


def set_modifier_input(modifier, identifier, value):
    """Assign a value to a Geometry Nodes modifier input socket."""
    inputs = _modifier_input_slots(modifier)
    if inputs is not None:
        input_slot = getattr(inputs, identifier)
        value_property = input_slot.bl_rna.properties["value"]
        if value_property.type == "ENUM" and type(value) is int:
            value = value_property.enum_items[value].identifier
        input_slot.value = value
    else:
        modifier[identifier] = value


def finalize_object_result(
    context,
    source_object,
    result_object,
    *,
    keep_source=False,
):
    """Activate a result object and optionally replace its source object."""
    source_name = source_object.name
    for selected in context.selected_objects:
        selected.select_set(False)
    result_object.select_set(True)
    context.view_layer.objects.active = result_object
    if not keep_source:
        bpy.data.objects.remove(source_object, do_unlink=True)
        result_object.name = source_name
    return result_object
