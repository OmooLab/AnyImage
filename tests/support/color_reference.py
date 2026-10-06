"""Create reference test data and own Blender reference registration."""

import bpy
import numpy as np
import pytest
from anyimage import properties
from anyimage.common import color_reference as reference_cache
from anyimage.operators.color_match import MatchColorReference


def create_rgba_image(name, rgba, *, floating=False):
    rgba = np.asarray(rgba, dtype=np.float32)
    image = bpy.data.images.new(
        name,
        width=rgba.shape[1],
        height=rgba.shape[0],
        alpha=True,
        float_buffer=floating,
    )
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    image.pack()
    image.update()
    return image


def create_image_empty(name, image):
    owner = bpy.data.objects.new(name, None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.scene.collection.objects.link(owner)
    return owner


@pytest.fixture(autouse=True)
def isolate_reference_cache():
    reference_cache.clear_color_references()
    yield
    reference_cache.clear_color_references()


@pytest.fixture
def registered_color_reference():
    try:
        bpy.utils.register_class(properties.AnyImageSettings)
        registered_settings = True
    except (RuntimeError, ValueError):
        registered_settings = False
    added_scene_property = not hasattr(bpy.types.Scene, "anyimage_settings")
    if added_scene_property:
        bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(
            type=properties.AnyImageSettings,
        )
    registered_operators = []
    for operator in (MatchColorReference,):
        try:
            bpy.utils.register_class(operator)
            registered_operators.append(operator)
        except (RuntimeError, ValueError):
            pass
    properties.register_color_references()
    yield
    properties.unregister_color_references()
    for operator in reversed(registered_operators):
        bpy.utils.unregister_class(operator)
    if added_scene_property:
        del bpy.types.Scene.anyimage_settings
    if registered_settings:
        bpy.utils.unregister_class(properties.AnyImageSettings)
