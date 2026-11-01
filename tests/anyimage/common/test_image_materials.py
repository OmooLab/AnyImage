from types import SimpleNamespace
import bpy
import numpy as np
import pytest


from anyimage.common import material as material_data
from tests.support.image_objects import _create_cutout_shape, _group_node


def test_generated_materials_use_implicit_uv_and_readable_layout():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = SimpleNamespace(name="Source")
    color = bpy.data.images.new("Color", width=4, height=2)
    normal = bpy.data.images.new("Normal", width=4, height=2)

    material = material_data.create_image_material(source, color, normal_image=normal)
    nodes = material.node_tree.nodes
    assert not any(node.bl_idname == "ShaderNodeUVMap" for node in nodes)
    assert all(not node.inputs["Vector"].is_linked for node in nodes if node.type == "TEX_IMAGE")
    texture_location = lambda image: tuple(next(
        node for node in nodes if node.type == "TEX_IMAGE" and node.image == image
    ).location)
    assert texture_location(color) == (-700.0, 300.0)
    assert texture_location(normal) == (-700.0, 0.0)
    assert tuple(next(node for node in nodes if node.type == "GROUP").location) == (-300.0, 300.0)
    assert tuple(next(node for node in nodes if node.type == "BSDF_PRINCIPLED").location) == (100.0, 300.0)
    assert tuple(next(node for node in nodes if node.type == "OUTPUT_MATERIAL").location) == (500.0, 300.0)
    layer = next(node for node in nodes if node.type == "GROUP")
    shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    assert layer.width == 190.0
    assert {
        (link.from_socket.name, link.to_socket.name)
        for link in material.node_tree.links
        if link.from_node == layer and link.to_node == shader
    } == {
        ("Color", "Base Color"), ("Emission", "Emission Color"),
        ("Alpha", "Alpha"), ("Normal", "Normal"),
        ("Roughness", "Roughness"),
    }

    panorama = material_data.create_image_material(
        source, color, shadeless=True, texture_extension="REPEAT")
    nodes = panorama.node_tree.nodes
    assert not any(node.bl_idname in {
        "ShaderNodeUVMap", "ShaderNodeSeparateXYZ", "ShaderNodeClamp", "ShaderNodeCombineXYZ",
    } for node in nodes)
    texture = next(node for node in nodes if node.type == "TEX_IMAGE")
    shader = next(node for node in nodes if node.type == "GROUP")
    output = next(node for node in nodes if node.type == "OUTPUT_MATERIAL")
    assert not texture.inputs["Vector"].is_linked
    assert texture.extension == "REPEAT"
    assert (tuple(texture.location), tuple(shader.location), tuple(output.location)) == (
        (-700.0, 300.0), (-300.0, 300.0), (100.0, 300.0))


def test_image_layer_switches_between_tangent_and_object_space_normal():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    assert material_data.IMAGE_MATERIAL_NODE_GROUP_NAME == "O Texture to Layer"
    group = material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME)
    normal = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == "Normal Texture"
    )
    assert tuple(normal.default_value) == (0.5, 0.5, 1.0, 1.0)
    bump_scale = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == "Bump Scale"
    )
    assert bump_scale.default_value == 0.0
    normal_scale = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == "Normal Scale"
    )
    assert normal_scale.default_value == 1.0
    object_space = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == "Object Space"
    )
    assert object_space.default_value is False
    normal_maps = {
        node.space for node in group.nodes if node.bl_idname == "ShaderNodeNormalMap"
    }
    assert normal_maps == {"TANGENT", "OBJECT"}
    assert all(
        not node.label
        for node in group.nodes
        if node.bl_idname in {"ShaderNodeNormalMap", "ShaderNodeMix"}
    )

    color = bpy.data.images.new("Color", width=2, height=2)
    normal_image = bpy.data.images.new("Normal", width=2, height=2)
    object_material = material_data.create_image_material(
        SimpleNamespace(name="Object Normal"),
        color,
        1.0,
        normal_image=normal_image,
        normal_space="OBJECT",
    )
    layer = _group_node(group, object_material.node_tree)
    assert layer.inputs["Object Space"].default_value is True

    tangent_material = material_data.create_image_material(
        SimpleNamespace(name="Tangent Normal"),
        color,
        1.0,
        normal_image=normal_image,
    )
    layer = _group_node(group, tangent_material.node_tree)
    assert layer.inputs["Object Space"].default_value is False
    reused = material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME)
    assert {
        node.space for node in reused.nodes if node.bl_idname == "ShaderNodeNormalMap"
    } == {"TANGENT", "OBJECT"}


def test_cutout_material_uses_ior_1_2():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Cutout", width=16, height=16, alpha=True)
    source = bpy.data.objects.new("Cutout", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)

    result = _create_cutout_shape(source, "FLAT", 0.1)

    shader = next(
        node
        for node in result.data.materials[0].node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    assert np.isclose(shader.inputs["IOR"].default_value, 1.2)
    image_layer = _group_node(
        material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME),
        result.data.materials[0].node_tree,
    )
    assert not shader.inputs["Specular IOR Level"].is_linked


def test_plane_material_uses_default_specular_and_supports_shadeless():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Plane", width=2, height=2, alpha=True)
    source = SimpleNamespace(data=SimpleNamespace(name="Plane"))

    material = material_data.create_image_material(source.data, image)
    shader = next(
        node
        for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    assert np.isclose(shader.inputs["IOR"].default_value, 1.2)
    image_layer = _group_node(material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME), material.node_tree)
    assert image_layer.inputs["Bump Scale"].default_value == 0.0
    assert not shader.inputs["Specular IOR Level"].is_linked

    shadeless = material_data.create_image_material(
        source.data,
        image,
        0.0,
        shadeless=True,
    )
    assert not any(
        node.bl_idname == "ShaderNodeBsdfPrincipled"
        for node in shadeless.node_tree.nodes
    )


def test_cutout_material_uses_flat_tangent_normal():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.objects.new("Source", None)
    source.empty_display_type = "IMAGE"
    source.data = bpy.data.images.new("Source", width=2, height=2)
    color = bpy.data.images.new("Color", width=2, height=2)
    normal = bpy.data.images.new("Normal", width=1, height=1)

    result = material_data.create_image_material(
        source.data,
        color,
        0.0,
        normal_image=normal,
        scene=bpy.context.scene,
    )

    layer = _group_node(material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME), result.node_tree)
    assert layer.inputs["Object Space"].default_value is False


def test_shared_conversion_images_use_blender_duplicate_suffix():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Poster", width=16, height=16)
    source = bpy.data.objects.new("Poster", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    bpy.context.collection.objects.link(source)

    other = source.copy()
    bpy.context.collection.objects.link(other)
    from tests.support.color_image import color_image
    first = color_image(source.data)
    second = color_image(source.data)

    assert first is not image
    assert second is not image
    assert first is not second
    assert first.name == "Poster_color.png"
    assert second.name == "Poster_color.png.001"


def test_panorama_normal_encoding_matches_image_layer_object_axes(tmp_path):
    from mathutils import Vector
    from tests.support.mesh_bake import render_material

    bpy.ops.wm.read_factory_settings(use_empty=True)
    expected = np.array((0.2, -0.3, 0.9))
    expected /= np.linalg.norm(expected)
    encoded = expected[[0, 2, 1]] * (1, 1, -1) * 0.5 + 0.5
    normal = bpy.data.images.new("Panorama normal", width=4, height=2, float_buffer=True)
    normal.colorspace_settings.is_data = True
    normal.pixels.foreach_set(np.tile(np.array((*encoded, 1), np.float32), 8))
    color = bpy.data.images.new("Color", width=4, height=2)
    material = material_data.create_image_material(
        color, color, normal_image=normal, normal_space="OBJECT", emission_strength=1)
    mesh = bpy.data.meshes.new("Normal probe")
    mesh.from_pydata([(-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(material)
    obj = bpy.data.objects.new("Normal probe", mesh)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = (0.2, 0.1, 0.4)
    bpy.context.view_layer.update()
    pixels = render_material(obj, tmp_path / "normal.exr", (0, 0, 1))
    actual = pixels[24:40, 24:40, :3] * 2 - 1
    rotated = np.array(obj.matrix_world.to_3x3() @ Vector(expected))
    np.testing.assert_allclose(actual, np.broadcast_to(rotated, actual.shape), atol=1e-5)


@pytest.mark.parametrize("is_float,color_space,expected", [(True, "Linear Rec.709", 4.0), (False, "sRGB", .21404114), (False, "Non-Color", .5)])
def test_emission_threshold_uses_visible_linear_median(is_float, color_space, expected):
    from anyimage.common.color_image import median_color_luminance
    from anyimage.common.image import COLOR_NORMALIZED_PROPERTY

    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Median", width=4, height=1, float_buffer=is_float)
    image.colorspace_settings.name = color_space
    values = [1, 4, 8, 100] if is_float else [.1, .5, .9, 1]
    image.pixels.foreach_set([c for i, value in enumerate(values) for c in (value, value, value, float(i < 3))])
    assert median_color_luminance(image) == pytest.approx(expected, abs=.005)
    if color_space == "sRGB":
        image[COLOR_NORMALIZED_PROPERTY] = True
    if is_float or color_space == "sRGB":
        material = material_data.create_image_material(image, image)
        layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
        assert layer.inputs["Emission Threshold"].default_value == pytest.approx(expected, abs=.005)
    image.pixels.foreach_set([0] * 16)
    assert median_color_luminance(image) == 0
