import bpy
import pytest
from nodes.O_AnyImage.O_AnyImage.shader.o_texture_to_layer import OTextureToLayer


def shadeless_material(image):
    """Set up a scene material using the bundled Shadeless group."""
    from anyimage.common.node import load_node_group

    material = bpy.data.materials.new("Shadeless")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    group = nodes.new("ShaderNodeGroup")
    group.node_tree = load_node_group("O Shadeless")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(texture.outputs["Color"], group.inputs["Color"])
    links.new(texture.outputs["Alpha"], group.inputs["Alpha"])
    links.new(group.outputs["Shader"], output.inputs["Surface"])
    return material


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
