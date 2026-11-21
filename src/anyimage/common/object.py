"""Shared Blender Object and Geometry Nodes Modifier helpers."""

import bpy

from .image import image_content_signature, image_pixels, is_image_empty, mark_image_empty_reference


def modifier_input_identifier(node_group, name, *, subtype=None):
    for item in node_group.interface.items_tree:
        if item.item_type != "SOCKET" or item.in_out != "INPUT":
            continue
        if item.name == name and (subtype is None or getattr(item, "subtype", None) == subtype):
            return item.identifier
    raise RuntimeError(f"Geometry Nodes input is missing: {name}")


def _modifier_input_slots(modifier):
    """Return RNA inputs on Blender 5.x; Blender 4.5 uses ID properties."""
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


def get_modifier_input(modifier, identifier):
    """Read a Geometry Nodes modifier input socket value."""
    inputs = _modifier_input_slots(modifier)
    if inputs is not None:
        return getattr(inputs, identifier).value
    return modifier.get(identifier)


def read_conversion_source(operator):
    """Return the captured source and the pixels used to validate it."""
    try:
        source = operator._source_object
        if is_image_empty(source) and source.data == operator._source_image:
            pixels = image_pixels(source.data)
            if image_content_signature(source.data, pixels) == operator._source_signature:
                return source, pixels
    except ReferenceError:
        pass
    raise RuntimeError("The conversion source image has changed")


def require_conversion_source(operator):
    """Validate the live object and image captured before conversion."""
    return read_conversion_source(operator)[0]


def remove_conversion_source(source_object):
    """Preserve the image reference when removing a converted object."""
    if is_image_empty(source_object):
        mark_image_empty_reference(source_object.data)
    bpy.data.objects.remove(source_object, do_unlink=True)


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
        remove_conversion_source(source_object)
        result_object.name = source_name
    return result_object
