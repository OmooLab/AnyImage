import bpy
import pytest
from nodes.O_AnyImage.O_AnyImage.shader.o_texture_to_layer import OTextureToLayer


@pytest.fixture(params=["CYCLES", "EEVEE"])
def render_engine(request):
    """Resolve the render engine identifier exposed by this Blender version."""
    if request.param == "CYCLES":
        return "CYCLES"
    return next(item.identifier for item in bpy.context.scene.render.bl_rna.properties["engine"].enum_items
                if item.identifier.startswith("BLENDER_EEVEE"))


@pytest.fixture
def image_layer():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = OTextureToLayer.create_group()
    yield group
    bpy.ops.wm.read_factory_settings(use_empty=True)
