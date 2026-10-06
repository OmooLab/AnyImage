import bpy
import pytest
from types import SimpleNamespace
from anyimage.common import material
from tests.support.materials import image_layer


@pytest.mark.parametrize("shadeless", [False, True])
def test_material_alpha_fix_defaults_to_zero_independently_of_preference(image_layer, monkeypatch, shadeless):
    enabled, view = True, "AgX"
    monkeypatch.setattr(material, "material_node_group", lambda depth_plane=False: image_layer)
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: enabled)
    color = bpy.data.images.new("Alpha edge", width=2, height=2, alpha=True)
    scene = SimpleNamespace(view_settings=SimpleNamespace(view_transform=view))
    result = material.create_image_material(color, color, shadeless=shadeless, scene=scene)
    if shadeless:
        shader = next(node for node in result.node_tree.nodes if node.type == "GROUP")
        assert shader.node_tree.name == "O Shadeless"
        assert shader.inputs["Color"].links[0].from_node.type == "TEX_IMAGE"
        assert shader.inputs["Alpha"].links[0].from_socket.name == "Alpha"
        assert len([node for node in result.node_tree.nodes if node.type == "GROUP"]) == 1
        return
    layer = next(node for node in result.node_tree.nodes if node.type == "GROUP" and node.node_tree == image_layer)
    assert layer.inputs["Alpha Fix"].default_value == 0
    alpha_link = layer.outputs["Alpha"].links[0]
    assert alpha_link.to_node.type == "BSDF_PRINCIPLED"
    assert alpha_link.to_socket.name == "Alpha"
    layer.inputs["Alpha Fix"].default_value = 0.5
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: not enabled)
    second = material.create_image_material(color, color, shadeless=shadeless, scene=scene)
    second_layer = next(node for node in second.node_tree.nodes if node.type == "GROUP" and node.node_tree == image_layer)
    assert second_layer.inputs["Alpha Fix"].default_value == 0
    assert layer.inputs["Alpha Fix"].default_value == 0.5
