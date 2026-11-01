"""Verify spatial panorama emission through baking and GLB export."""

import json
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import bpy
import numpy as np
import pytest

from anyimage.common.image import COLOR_NORMALIZED_PROPERTY, image_pixels
from anyimage.common.material import create_image_material
from anyimage.operators.bake_mesh import BakeMesh, materialization, materials
from anyimage.operators.bake_mesh.textures import create_emission_color_image
from nodes.O_AnyImage.O_AnyImage.shader.o_texture_to_layer import OTextureToLayer
from tests.support.mesh_bake import render_material
from tests.support.panorama import panorama


@pytest.fixture
def image_object():
    obj, _ = panorama(depth=np.linspace(.8, 1.3, 128)[None, :], subdivide=2)
    obj.data.from_pydata([(0, 0, 0)], [], [])
    OTextureToLayer.create_group()
    image = bpy.data.images.new("Panorama color", width=128, height=64, alpha=True)
    image.colorspace_settings.name = "sRGB"
    image[COLOR_NORMALIZED_PROPERTY] = True
    pixels = np.ones((64, 128, 4), np.float32)
    pixels[..., 1] = .5 + .3 * np.sin(2 * np.pi * (np.arange(128) + .5) / 128)
    pixels[..., 2] = (.2 + .3 * (np.arange(64) + .5) / 64)[:, None]
    image.pixels.foreach_set(pixels.ravel())
    material = create_image_material(image, image, texture_extension="REPEAT", emission_strength=1)
    # A user-authored strength graph remains bakeable alongside geometry attributes.
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    layer = next(n for n in nodes if n.type == "GROUP")
    links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
    strength = nodes.new("ShaderNodeMath")
    strength.operation = "ADD"
    strength.inputs[1].default_value = 1
    coordinates = nodes.new("ShaderNodeTexCoord")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coordinates.outputs["UV"], separate.inputs[0])
    links.new(separate.outputs["Y"], strength.inputs[0])
    links.new(strength.outputs[0], shader.inputs["Emission Strength"])
    obj.data.materials.append(material)
    obj["o_image_object"] = True
    obj.location = (.1, .2, .1)
    obj.rotation_euler.z = .4
    obj.scale = (1.2, .8, 1)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    layer = next(node for node in material.node_tree.nodes if node.type == "GROUP")
    for name in ("Roughness", "Alpha", "Normal"):
        for link in tuple(layer.outputs[name].links):
            material.node_tree.links.remove(link)
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    yield obj
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("shared", [False, True])
def test_panorama_emission_bakes_and_roundtrips_glb(image_object, shared, tmp_path):
    import addon_utils

    obj = image_object
    original = obj.active_material
    if shared:
        other = obj.copy()
        other.data = obj.data.copy()
        bpy.context.collection.objects.link(other)
        other.hide_render = True
        other.select_set(False)
    direction = (-1, 0, 0) if shared else (0, -1, 0)
    before = render_material(obj, tmp_path / "before.exr", direction, channel="Emission")
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    shader = next(n for n in obj.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert not any(n.type in {"TEX_COORD", "SEPXYZ", "MATH"} for n in obj.active_material.node_tree.nodes)
    strength = shader.inputs["Emission Strength"].default_value
    assert not shader.inputs["Emission Strength"].is_linked and strength > 1
    image = shader.inputs["Emission Color"].links[0].from_node.image
    assert image != shader.inputs["Base Color"].links[0].from_node.image
    assert image.name.endswith("_emissioncolor.png")
    assert image.colorspace_settings.name == "sRGB" and not image.is_float
    assert bytes(image.packed_file.data).startswith(b"\x89PNG\r\n\x1a\n")
    assert np.unique(image_pixels(image).reshape(-1, 4)[:, 0]).size > 1
    if shared:
        assert other.active_material == original and obj.active_material != original
        original_shader = next(n for n in original.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        assert original_shader.inputs["Emission Strength"].is_linked
    after = render_material(obj, tmp_path / "after.exr", direction, channel="Emission")
    from scipy.ndimage import binary_erosion
    visible = binary_erosion(before[..., 0] > 1, iterations=3)
    assert visible.any()
    np.testing.assert_allclose(after[visible, :3], before[visible, :3], atol=.02)
    addon_utils.enable("io_scene_gltf2")
    path = tmp_path / "emission.glb"
    assert bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True) == {"FINISHED"}
    data = path.read_bytes()
    material = json.loads(data[20:20 + struct.unpack_from("<I", data, 12)[0]])["materials"][0]
    assert "emissiveTexture" in material
    assert material["extensions"]["KHR_materials_emissive_strength"]["emissiveStrength"] == pytest.approx(strength)
    assert max(material["emissiveFactor"]) <= 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.gltf(filepath=str(path)) == {"FINISHED"}
    imported = next(n for m in bpy.data.materials for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert imported.inputs["Emission Strength"].default_value == pytest.approx(strength)
    assert imported.inputs["Emission Color"].is_linked


@pytest.mark.parametrize("stage", ["encoding", "layout"])
def test_emission_failure_restores_strength_links_and_images(image_object, monkeypatch, stage):
    obj = image_object
    tree = obj.active_material.node_tree
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    strength = shader.inputs["Emission Strength"].default_value
    links = {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    counts = tuple(len(items) for items in (bpy.data.images, bpy.data.meshes, bpy.data.materials, bpy.data.scenes, bpy.data.node_groups))
    image = next(n.image for n in tree.nodes if n.type == "TEX_IMAGE")
    pixels = image_pixels(image)

    def fail(*args):
        raise RuntimeError("Injected emission failure")

    if stage == "encoding":
        monkeypatch.setattr(materialization, "create_emission_color_image", fail)
    else:
        monkeypatch.setattr(materials, "arrange_material_textures", fail)
    with pytest.raises(RuntimeError, match="Injected emission"):
        materialization.materialize_mesh_and_textures(bpy.context, obj)
    assert shader.inputs["Emission Strength"].default_value == strength
    assert links == {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    assert counts == tuple(len(items) for items in (bpy.data.images, bpy.data.meshes, bpy.data.materials, bpy.data.scenes, bpy.data.node_groups))
    np.testing.assert_array_equal(image_pixels(image), pixels)


def test_emission_encoding_preserves_hdr_ratios(image_object):
    from anyimage.common.color_space import srgb_to_linear_rgb

    source = bpy.data.images.new("Linear emission", width=3, height=1, alpha=True, float_buffer=True)
    source.colorspace_settings.name = "Non-Color"
    pixels = np.array([[1, .5, .25, 1], [10, 5, 2.5, 1], [100, 50, 25, 1]], np.float32)
    source.pixels.foreach_set(pixels.ravel())
    result, strength = create_emission_color_image(source)
    assert strength == 100
    restored = srgb_to_linear_rgb(image_pixels(result).reshape(-1, 4)[:, :3]) * strength
    np.testing.assert_allclose(restored, pixels[:, :3], rtol=.025, atol=.01)


def test_inverse_mask_emission_survives_baking(image_object, tmp_path):
    from anyimage.common.object import modifier_input_identifier, set_modifier_input
    from scipy.ndimage import binary_erosion

    obj = image_object
    modifier = obj.modifiers[0]
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Depth Mask"), False)
    depth = bpy.data.images["Radial Depth"]
    pixels = image_pixels(depth).reshape(64, 128, 4)
    pixels[..., 3] = np.linspace(0, 1, 128)[None, :]
    depth.pixels.foreach_set(pixels.ravel())
    tree = obj.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    layer.inputs["Emission Threshold"].default_value = .1
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    for link in tuple(shader.inputs["Emission Strength"].links):
        tree.links.remove(link)
    shader.inputs["Emission Strength"].default_value = 1
    tree.links.new(layer.outputs["Emission"], shader.inputs["Emission Color"])
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    before = render_material(obj, tmp_path / "mask-before.exr", (0, -1, 0), channel="Emission")
    assert np.ptp(before[..., 0]) > .1
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    assert "o_emission" not in obj.data.attributes
    after = render_material(obj, tmp_path / "mask-after.exr", (0, -1, 0), channel="Emission")
    visible = binary_erosion(before[..., 0] > .05, iterations=3)
    assert visible.any()
    np.testing.assert_allclose(after[visible, :3], before[visible, :3], atol=.025)
