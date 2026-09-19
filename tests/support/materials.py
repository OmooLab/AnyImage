import bpy
import pytest
from nodes.groups.image_layer import build_image_layer_group


@pytest.fixture
def image_layer():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = build_image_layer_group()
    yield group
    bpy.ops.wm.read_factory_settings(use_empty=True)
