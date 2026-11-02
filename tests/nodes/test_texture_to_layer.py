"""Check saved texture-layer color mappings through rendered shader outputs."""
import bpy
import numpy as np
import pytest

from anyimage.common.material import create_image_material
from anyimage.common.node import load_node_group
from tests.support.mesh_bake import render_material


def test_bump_direction_and_shared_height(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Bump ramp", width=64, height=64, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    rgba = np.ones((64, 64, 4), np.float32)
    rgba[..., :3] = np.linspace(.01, 1, 64)[None, :, None]
    image.pixels.foreach_set(rgba.ravel())
    material = create_image_material(image, image)
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    bump = next(n for n in layer.node_tree.nodes if n.type == "BUMP")
    height = bump.inputs["Height"].links[0].from_node
    while height.type == "REROUTE":
        height = height.inputs[0].links[0].from_node
    assert height.operation == "DIVIDE"
    bpy.ops.mesh.primitive_plane_add(size=4)
    obj = bpy.context.object
    obj.data.materials.append(material)
    layer.inputs["Highlight Threshold"].default_value = 2
    normals = {}
    for scale in (0, 10, -10):
        layer.inputs["Bump Scale"].default_value = scale
        pixels = render_material(obj, tmp_path / f"bump{scale}.exr", (0, 0, 1))
        normals[scale] = pixels[24:40, 24:40, :3] * 2 - 1
    np.testing.assert_allclose(normals[0], np.broadcast_to([0, 0, 1], normals[0].shape), atol=1e-5)
    assert np.max(np.abs(normals[10][..., 0])) > .0001
    np.testing.assert_allclose(normals[10][..., :2], -normals[-10][..., :2], atol=1e-5)
    np.testing.assert_allclose(normals[10][..., 2], normals[-10][..., 2], atol=1e-5)
    layer.inputs["Bump Scale"].default_value = 10
    roughness = []
    tilts = []
    for threshold in (2, .2, .001):
        layer.inputs["Highlight Threshold"].default_value = threshold
        pixels = render_material(obj, tmp_path / f"highlight{threshold}.exr", (0, 0, 1))
        tilts.append(np.mean(np.abs(pixels[24:40, 24:40, 0] * 2 - 1)))
        pixels = render_material(obj, tmp_path / f"roughness{threshold}.exr", (0, 0, 1), channel="Roughness")
        roughness.append(pixels[24:40, 24:40, :3])
    assert tilts[0] > tilts[1] > tilts[2]
    assert tilts[2] < 1e-5
    np.testing.assert_array_equal(roughness[0], roughness[1])
    np.testing.assert_array_equal(roughness[0], roughness[2])


def test_texture_layer_controls():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = load_node_group("O Texture to Layer")
    inputs = {item.name: item for item in group.interface.items_tree
              if item.item_type == "SOCKET" and item.in_out == "INPUT"}
    roughness = inputs["Roughness Scale"]
    assert (roughness.default_value, roughness.max_value, roughness.subtype) == (1, 1, "FACTOR")
    assert (inputs["Bump Scale"].min_value, inputs["Bump Scale"].max_value) == (-10, 10)
    assert inputs["Bump Scale"].default_value == 1
    assert inputs["Alpha Scale"].subtype == "FACTOR"
    assert tuple(inputs["Normal Texture"].default_value) == (0.5, 0.5, 1, 1)
    assert inputs["Normal Scale"].default_value == 1
    assert inputs["Normal Scale"].max_value == 2
    assert inputs["Object Space"].default_value is False
    assert inputs["Highlight Threshold"].parent.name == "Options"
    mapping = next(link.to_node for link in group.links
                   if link.from_node.type == "GROUP_INPUT" and link.from_socket.name == "Roughness Scale")
    assert mapping.inputs["To Min"].default_value == 1.5
    assert mapping.inputs["From Max"].default_value == 1


@pytest.mark.parametrize("brightness,background,scale", [(0.0, 0.0, 1.0), (.25, 0.0, .5), (1.0, 1.0, .5), (2.5, 0.0, 1.0), (4.0, 2.0, 1.0)])
@pytest.mark.parametrize("emission_weight", [0.0, .4, 1.0])
def test_texture_layer_mappings(tmp_path, brightness, background, scale, emission_weight):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Linear texture", width=4, height=4, float_buffer=True)
    image.colorspace_settings.is_data = True
    image.pixels.foreach_set([brightness, brightness, brightness, .8] * 16)
    material = create_image_material(image, image, emission_strength=1)
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Highlight Threshold"].default_value = 1.0
    layer.inputs["Alpha Background"].default_value = background
    layer.inputs["Alpha Scale"].default_value = scale
    bpy.ops.mesh.primitive_plane_add(size=4)
    obj = bpy.context.object
    obj.data.materials.append(material)
    obj.data.attributes.new("o_emission", "FLOAT", "CORNER").data.foreach_set("value", [emission_weight] * 4)
    expected_alpha = min(abs(brightness - background) / max(background, 1), 1) ** (1 - scale) * .8
    factor = np.clip((brightness - 1) / 3, 0, 1)
    expected_emission = min(brightness * (factor ** 3 * (factor * (factor * 6 - 15) + 10) + emission_weight), 4)
    compressed = brightness / (brightness + .1)
    dark_roughness = 1 - compressed ** 3 * (compressed * (compressed * 6 - 15) + 10)
    expected_roughness = min((.255 - .49 * (compressed - .5)) ** .5 + dark_roughness, 1)
    for channel, expected in (("Alpha", expected_alpha), ("Roughness", expected_roughness), ("Emission", expected_emission)):
        pixels = render_material(obj, tmp_path / f"{channel}.exr", (0, 0, 1), channel=channel)
        np.testing.assert_allclose(pixels[24:40, 24:40, :3], expected, atol=1e-3)


def test_emission_limit_per_channel(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("HDR color", width=4, height=4, float_buffer=True)
    image.colorspace_settings.is_data = True
    image.pixels.foreach_set([.25, 2.0, 16.0, 1.0] * 16)
    material = create_image_material(image, image, emission_strength=1)
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Highlight Threshold"].default_value = .0001
    bpy.ops.mesh.primitive_plane_add(size=4)
    obj = bpy.context.object
    obj.data.materials.append(material)
    obj.data.attributes.new("o_emission", "FLOAT", "CORNER").data.foreach_set("value", [1.0] * 4)
    pixels = render_material(obj, tmp_path / "limited_emission.exr", (0, 0, 1), channel="Emission")
    expected = np.broadcast_to([.5, 4.0, 4.0], pixels[24:40, 24:40, :3].shape)
    np.testing.assert_allclose(pixels[24:40, 24:40, :3], expected, atol=1e-3)
