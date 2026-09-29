from types import SimpleNamespace
import bpy
import numpy as np


from anyimage.common import image as image_data
from anyimage.common import material as material_data
from tests.support.image_objects import _create_cutout_shape, _group_node


def test_generated_materials_use_implicit_uv_and_readable_layout():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = SimpleNamespace(name="Source")
    color = bpy.data.images.new("Color", width=4, height=2)
    normal = bpy.data.images.new("Normal", width=4, height=2)
    depth = bpy.data.images.new("Depth", width=4, height=2)

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

    depth_material = material_data.create_image_material(
        source,
        color,
        displacement_image=depth,
        displacement_midlevel=0.5,
        displacement_scale=2.0,
    )
    nodes = depth_material.node_tree.nodes
    assert not any(node.bl_idname == "ShaderNodeUVMap" for node in nodes)
    assert all(not node.inputs["Vector"].is_linked for node in nodes if node.type == "TEX_IMAGE")
    depth_texture = next(node for node in nodes if node.type == "TEX_IMAGE" and node.image == depth)
    assert tuple(depth_texture.location) == (-1200.0, -300.0)
    math_locations = {node.operation: tuple(node.location) for node in nodes if node.type == "MATH"}
    assert math_locations == {
        "SUBTRACT": (-950.0, -300.0),
        "MULTIPLY": (-700.0, -300.0),
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

    assert material_data.IMAGE_MATERIAL_NODE_GROUP_NAME == "O Image Layer"
    group = material_data.material_node_group()
    normal = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET"
        and item.in_out == "INPUT"
        and item.name == "Normal"
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
    reused = material_data.material_node_group()
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
        material_data.material_node_group(),
        result.data.materials[0].node_tree,
    )
    ior_level_link = next(
        link
        for link in result.data.materials[0].node_tree.links
        if link.to_node == shader
        and link.to_socket == shader.inputs["Specular IOR Level"]
    )
    assert ior_level_link.from_node == image_layer
    assert ior_level_link.from_socket == image_layer.outputs["Color"]


def test_plane_material_color_drives_ior_level_but_shadeless_does_not():
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
    image_layer = _group_node(material_data.material_node_group(), material.node_tree)
    assert image_layer.inputs["Bump Scale"].default_value == 0.0
    assert any(
        link.from_node == image_layer
        and link.from_socket == image_layer.outputs["Color"]
        and link.to_node == shader
        and link.to_socket == shader.inputs["Specular IOR Level"]
        for link in material.node_tree.links
    )

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

    layer = _group_node(material_data.material_node_group(), result.node_tree)
    assert layer.inputs["Object Space"].default_value is False


def test_loaded_normal_image_uses_normal_texture_name(tmp_path):
    from PIL import Image

    path = tmp_path / "normal.png"
    Image.new("RGB", (1, 1), (128, 128, 255)).save(path)
    source = SimpleNamespace(data=SimpleNamespace(name="Poster.png"))

    image = image_data.load_normal_result_image(path, source)

    assert image.name == "Poster_normal.png"
    assert image.colorspace_settings.name == "Non-Color"
    assert image.packed_file is not None


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
