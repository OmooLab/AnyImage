import bpy
import numpy as np
import pytest


from anyimage.common import material as material_data
from tests.support.image_objects import _create_cutout_shape, _group_node


def test_generated_materials_use_implicit_uv_and_readable_layout():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.images.new("Source", width=4, height=2)
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
    group = material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME)
    color = bpy.data.images.new("Color", width=2, height=2)
    normal_image = bpy.data.images.new("Normal", width=2, height=2)
    for space in ("OBJECT", "TANGENT"):
        material = material_data.create_image_material(
            color, color, normal_image=normal_image, normal_space=space,
        )
        layer = _group_node(group, material.node_tree)
        assert layer.inputs["Object Space"].default_value == (space == "OBJECT")
    assert {
        node.space for node in group.nodes if node.type == "NORMAL_MAP"
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
    assert not shader.inputs["Specular IOR Level"].is_linked


def test_plane_material_uses_default_specular_and_supports_shadeless():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Plane", width=2, height=2, alpha=True)

    material = material_data.create_image_material(image, image)
    shader = next(
        node
        for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    assert np.isclose(shader.inputs["IOR"].default_value, 1.2)
    image_layer = _group_node(material_data.load_node_group(material_data.IMAGE_MATERIAL_NODE_GROUP_NAME), material.node_tree)
    assert image_layer.inputs["Bump Scale"].default_value == 1.0
    assert not shader.inputs["Specular IOR Level"].is_linked

    shadeless = material_data.create_image_material(
        image,
        image,
        shadeless=True,
    )
    assert not any(
        node.bl_idname == "ShaderNodeBsdfPrincipled"
        for node in shadeless.node_tree.nodes
    )


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


@pytest.mark.parametrize("has_normal", [False, True])
def test_object_normal_material_uses_image_or_geometry_and_follows_object_rotation(tmp_path, has_normal):
    from mathutils import Vector
    from tests.support.mesh_bake import render_material

    bpy.ops.wm.read_factory_settings(use_empty=True)
    expected = np.array((0.2, -0.3, 0.9))
    expected /= np.linalg.norm(expected)
    encoded = expected * 0.5 + 0.5
    normal = bpy.data.images.new("Object normal", width=4, height=2, float_buffer=True)
    normal.colorspace_settings.is_data = True
    normal.pixels.foreach_set(np.tile(np.array((*encoded, 1), np.float32), 8))
    color = bpy.data.images.new("Color", width=4, height=2)
    material = material_data.create_image_material(
        color, color, normal_image=normal if has_normal else None, normal_space="OBJECT", emission_strength=1)
    if not has_normal:
        expected = np.array((0, 0, 1))
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
