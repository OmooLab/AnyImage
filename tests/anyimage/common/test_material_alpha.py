import bpy
from types import SimpleNamespace
from anyimage.common import material
from tests.support.materials import image_layer


def test_material_alpha_scale_defaults_to_one(image_layer):
    view = "AgX"
    color = bpy.data.images.new("Alpha edge", width=2, height=2, alpha=True)
    scene = SimpleNamespace(view_settings=SimpleNamespace(view_transform=view))
    result = material.create_image_material(color, color, scene=scene)
    layer = next(node for node in result.node_tree.nodes if node.type == "GROUP" and node.node_tree == image_layer)
    assert layer.inputs["Alpha Scale"].default_value == 1
    alpha_link = layer.outputs["Alpha"].links[0]
    assert alpha_link.to_node.type == "BSDF_PRINCIPLED"
    assert alpha_link.to_socket.name == "Alpha"
    layer.inputs["Alpha Scale"].default_value = 0.5
    second = material.create_image_material(color, color, scene=scene)
    second_layer = next(node for node in second.node_tree.nodes if node.type == "GROUP" and node.node_tree == image_layer)
    assert second_layer.inputs["Alpha Scale"].default_value == 1
    assert layer.inputs["Alpha Scale"].default_value == 0.5
