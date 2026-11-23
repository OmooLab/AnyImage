"""Validate conversion sources and replace them with result objects."""

import bpy

from .image import is_image_empty


def conversion_source(operator, scene=None):
    """Return the original Empty if it still holds the submitted image."""
    try:
        source = operator._source_object
        if is_image_empty(source) and source.data == operator._source_image:
            if scene is not None and (scene != operator._scene or source.name not in scene.objects):
                raise RuntimeError("The conversion source is no longer in this scene")
            return source
    except ReferenceError:
        pass
    raise RuntimeError("The conversion source image has changed")


def finalize_object_result(
    context,
    source_object,
    result_object,
):
    """Replace the source object and activate its result."""
    source_name = source_object.name
    for selected in context.selected_objects:
        selected.select_set(False)
    result_object.select_set(True)
    context.view_layer.objects.active = result_object
    bpy.data.objects.remove(source_object, do_unlink=True)
    result_object.name = source_name
    return result_object
