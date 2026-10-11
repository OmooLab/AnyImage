import bpy
import pytest
from nodes.O_AnyImage.O_AnyImage.shader.o_image_layer import OImageLayer


@pytest.fixture
def image_layer():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = OImageLayer.create_group()
    yield group
    bpy.ops.wm.read_factory_settings(use_empty=True)
