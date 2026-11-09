"""Verify static texture conversion, source isolation and attribute cleanup."""

import bpy
import numpy as np
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from anyimage.common import color_image as color_images
from anyimage.common.image import image_content_state, image_pixels
from anyimage.common.material import create_image_material
from anyimage.common.object import modifier_input_identifier, set_modifier_input
from anyimage.operators.bake_mesh.materialization import materialize_mesh_and_textures, PROTOCOL_ATTRIBUTES
from anyimage.operators.bake_mesh import BakeMesh
from nodes.O_AnyImage.O_AnyImage.geometry.o_cutout import OCutout
from nodes.O_AnyImage.O_AnyImage.shader.o_texture_to_layer import OTextureToLayer
from tests.support.depth_symmetry import symmetry
from tests.support.materials import render_engine
from tests.support.mesh_bake import add_post_bake_modifiers, mesh_geometry, modifier_inputs, render_material


@pytest.fixture
def cutout():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OTextureToLayer.create_group()
    mesh = bpy.data.meshes.new("Cutout")
    mesh.from_pydata([(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for item, value in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        item.uv = value
    mesh.attributes.new("user_value", "FLOAT", "POINT").data.foreach_set("value", [1, 2, 3, 4])
    color = bpy.data.images.new("Color", width=64, height=64, alpha=True, float_buffer=True)
    color.colorspace_settings.name = "Non-Color"
    pixels = np.ones((64, 64, 4), dtype=np.float32)
    pixels[..., 0] = np.linspace(0, 2, 64)[None, :]
    pixels[..., 1] = .2
    color.pixels.foreach_set(pixels.ravel())
    normal = bpy.data.images.new("Normal", width=64, height=64, float_buffer=True)
    normal.colorspace_settings.name = "Non-Color"
    normal.pixels.foreach_set(np.tile(np.array([.7, .6, .95, 1], dtype=np.float32), 64 * 64))
    material = create_image_material(color, color, normal_image=normal)
    mesh.materials.append(material)
    obj = bpy.data.objects.new("Cutout", mesh)
    obj["o_image_object"] = True
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Cutout", "NODES")
    modifier.node_group = OCutout.create_group()
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Mode"), 1)
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"), .2)
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    yield obj
    bpy.ops.wm.read_factory_settings(use_empty=True)


def test_materialization_reuses_material_and_preserves_source_geometry(cutout):
    source_mesh = cutout.data
    source_material = cutout.active_material
    source_scene = bpy.context.window.scene
    source_selection = list(bpy.context.selected_objects)
    source_material.node_tree.nodes.new("ShaderNodeGroup")
    source_textures = [n.image for n in source_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    for image in source_textures:
        image.filepath_raw = "//" + image.name + ".exr"
    source_images = {image.name: image.as_pointer() for image in bpy.data.images}
    result = materialize_mesh_and_textures(bpy.context, cutout)
    assert result is not None
    assert cutout.data == source_mesh and len(cutout.modifiers) == 1
    assert result.materials[0] == source_material
    assert not (set(result.attributes.keys()) & PROTOCOL_ATTRIBUTES)
    assert "user_value" in result.attributes
    assert list(result.uv_layers.keys()) == ["UVMap"]
    assert not any(n.type == "GROUP" and n.node_tree is not None for n in result.materials[0].node_tree.nodes)
    assert next(n for n in source_material.node_tree.nodes if n.type == "NORMAL_MAP").inputs["Strength"].default_value == 1
    images = [n.image for n in result.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"]
    assert all(i.packed_file is not None for i in images)
    assert all(tuple(i.size) == (64, 128) for i in images)
    assert max(images[0].pixels[:]) <= 1
    assert images[0].colorspace_settings.name == "sRGB" and not images[0].is_float
    assert all(bpy.data.images[name].as_pointer() == pointer for name, pointer in source_images.items())
    assert images[:2] == source_textures and len(images) == 3
    assert {image.name for image in images[2:]} == {"Color_roughness.png"}
    assert all(image.filepath_raw == "//" + image.name + ".exr" for image in source_textures), [(image.name, image.filepath_raw) for image in source_textures]
    assert len(bpy.data.scenes) == 1
    assert bpy.context.window.scene == source_scene
    assert bpy.context.object == cutout and list(bpy.context.selected_objects) == source_selection
    assert not any(g.name.endswith('.001') for g in bpy.data.node_groups)


@pytest.mark.parametrize("sharing", ["mesh", "material", "images"])
def test_bake_isolates_other_object_textures(cutout, sharing):
    cutout.active_material.name = "cat"
    other = cutout.copy()
    if sharing != "mesh":
        other.data = cutout.data.copy()
    if sharing == "images":
        other.data.materials[0] = cutout.active_material.copy()
    bpy.context.collection.objects.link(other)
    source_material = cutout.active_material
    source_images = [n.image for n in other.active_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    contents = [(tuple(image.size), image_pixels(image).copy()) for image in source_images]
    source_layer = next(n for n in source_material.node_tree.nodes if n.type == "GROUP")
    source_layer.inputs["Object Space"].default_value = True
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    assert other["o_image_object"] is True and len(other.modifiers) == 1
    other_layer = next(n for n in other.active_material.node_tree.nodes if n.type == "GROUP")
    assert other_layer.node_tree.name == "O Texture to Layer"
    if sharing != "images":
        assert source_layer.inputs["Object Space"].default_value is True
    assert (cutout.active_material == source_material) is (sharing == "images")
    assert cutout.active_material.name == ("cat" if sharing == "images" else "cat.001")
    results = [n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    assert all(result != source for result, source in zip(results, source_images))
    assert all(tuple(result.size) == (64, 128) and result.packed_file for result in results)
    for image, (size, pixels) in zip(source_images, contents):
        assert tuple(image.size) == size
        np.testing.assert_array_equal(image_pixels(image), pixels)


@pytest.mark.parametrize("object_space,bump,transformed", [
    (False, 0, False), (False, .08, True), (True, .08, True),
])
def test_static_normal_matches_shader_after_attributes_are_removed(cutout, tmp_path, object_space, bump, transformed):
    if transformed:
        cutout.rotation_euler = (.1, .2, .15)
        cutout.scale = (.8, 1.2, .9)
        bpy.context.view_layer.update()
    layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Object Space"].default_value = object_space
    layer.inputs["Normal Scale"].default_value = 1 if object_space else .6
    layer.inputs["Bump Scale"].default_value = bump
    directions = ((0, -1, 0), (0, 1, 0), (1, -.2, 0))
    before = [render_material(cutout, tmp_path / f"before-{i}.exr", d, with_uv_coverage=True) for i, d in enumerate(directions)]
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    after = [render_material(cutout, tmp_path / f"after-{i}.exr", d, with_uv_coverage=True) for i, d in enumerate(directions)]
    for direction, (original, source_coverage), (static, target_coverage) in zip(directions, before, after):
        np.testing.assert_array_equal(source_coverage, target_coverage)
        assert np.isfinite(static[source_coverage >= 0]).all()
        if direction == directions[-1]:
            assert np.count_nonzero(source_coverage == 0) > 0
        visible = source_coverage == 1
        from scipy.ndimage import binary_erosion
        visible = binary_erosion(visible, iterations=2)
        differences = np.linalg.norm(original[visible, :3] - static[visible, :3], axis=-1)
        assert len(differences) > 20
        assert np.quantile(differences, .95) < .04, (object_space, direction, original[32, 32], static[32, 32], np.quantile(differences, [.5, .95, 1]))


@pytest.mark.parametrize("thickness", [0, .15])
def test_depth_symmetry_materializes_regions_and_normals(symmetry, tmp_path, thickness):
    obj, _, _, set_cutout, set_mirror = symmetry
    obj["o_image_object"] = True
    OTextureToLayer.create_group()
    set_cutout("Mode", 1)
    set_cutout("Thickness", thickness, subtype="DISTANCE")
    set_cutout("Depth Scale", .5)
    set_mirror("Direction", (.15, .05, 1))
    set_mirror("Smooth", 2)
    set_mirror("Scale", .6)
    color = bpy.data.images.new("Color", width=128, height=128, float_buffer=True)
    color.pixels.foreach_set(np.tile(np.array([.8, .3, .2, 1], dtype=np.float32), 128 * 128))
    normal = bpy.data.images.new("Normal", width=128, height=128, float_buffer=True)
    normal.colorspace_settings.name = "Non-Color"
    y, x = np.mgrid[:128, :128]
    normals = np.stack((.3 + .12 * np.sin(x * .3), -.8 + .1 * np.cos(y * .4),
                        .5 + .1 * np.sin((x + y) * .2)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    normal.pixels.foreach_set(np.dstack((normals * .5 + .5, np.ones((128, 128)))).astype(np.float32).ravel())
    obj.data.materials.append(create_image_material(color, color, normal_image=normal, normal_space="OBJECT"))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    prefix_geometry = mesh_geometry(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data)
    trailing = add_post_bake_modifiers(obj, bpy.data.images["Depth"])
    final_geometry = mesh_geometry(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data)
    directions = ((1, 0, 0), (-1, 0, 0))
    before = [render_material(obj, tmp_path / f"s-before-{i}.exr", d) for i, d in enumerate(directions)]
    result = materialize_mesh_and_textures(bpy.context, obj)
    np.testing.assert_allclose(mesh_geometry(result)[0], prefix_geometry[0], atol=1e-6)
    assert mesh_geometry(result)[1] == prefix_geometry[1]
    assert not set(result.attributes.keys()) & PROTOCOL_ATTRIBUTES
    normal_result = next(n.image for n in result.materials[0].node_tree.nodes
                         if n.type == "TEX_IMAGE" and n.image.colorspace_settings.name == "Non-Color")
    assert tuple(normal_result.size) == ((256, 256) if thickness else (256, 128))
    obj.data = result
    for modifier in tuple(obj.modifiers)[:2]:
        obj.modifiers.remove(modifier)
    assert tuple(obj.modifiers) == trailing
    actual_geometry = mesh_geometry(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data)
    np.testing.assert_allclose(actual_geometry[0], final_geometry[0], atol=1e-6)
    assert actual_geometry[1] == final_geometry[1]
    for i, (direction, original) in enumerate(zip(directions, before)):
        static = render_material(obj, tmp_path / f"s-after-{i}.exr", direction)
        from scipy.ndimage import binary_erosion
        visible = binary_erosion(original[..., :3].max(axis=-1) > .01, iterations=2)
        differences = np.linalg.norm(original[visible, :3] - static[visible, :3], axis=-1)
        assert len(differences)
        assert np.quantile(differences, .95) < .04, (thickness, direction, np.quantile(differences, [.5, .95, 1]))


@pytest.mark.parametrize("mirrored,retained_user", [(False, False), (True, False), (True, True)])
def test_depth_cutout_conversion_removes_unused_depth(symmetry, mirrored, retained_user):
    obj, _, mirror, *_ = symmetry
    if not mirrored:
        obj.modifiers.remove(mirror)
    obj["o_image_object"] = True
    OTextureToLayer.create_group()
    color = bpy.data.images.new("Color", width=16, height=16, float_buffer=True)
    obj.data.materials.append(create_image_material(color, color))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    depth_name = "Depth"
    assert depth_name in bpy.data.images
    trailing = add_post_bake_modifiers(obj, bpy.data.images[depth_name] if retained_user else None)
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    assert (depth_name in bpy.data.images) is retained_user
    assert tuple(obj.modifiers) == trailing
    assert color.name in bpy.data.images


@pytest.mark.parametrize("execution", ["EXEC_DEFAULT", "INVOKE_DEFAULT"])
def test_conversion_operator_undo_redo(cutout, execution):
    name, mesh_name = cutout.name, cutout.data.name
    other = cutout.copy()
    bpy.context.collection.objects.link(other)
    other_name = other.name
    material_name = cutout.active_material.name
    source_color_name = next(n.image.name for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE")
    original_pixels = image_pixels(bpy.data.images[source_color_name]).copy()
    trailing = add_post_bake_modifiers(cutout)
    names = [m.name for m in trailing]
    group_name = trailing[1].node_group.name
    bpy.context.preferences.edit.use_global_undo = True
    bpy.utils.register_class(BakeMesh)
    try:
        bpy.ops.ed.undo_push(message="Before Bake Mesh")
        assert bpy.ops.anyimage.bake_mesh(execution, True) == {"FINISHED"}
        assert [m.name for m in bpy.data.objects[name].modifiers] == names
        assert "o_image_object" not in bpy.data.objects[name]
        assert bpy.data.objects[other_name].data.name == mesh_name
        assert bpy.data.objects[other_name].active_material.name == material_name
        assert bpy.data.objects[name].active_material != bpy.data.objects[other_name].active_material
        converted_color_name = next(n.image.name for n in bpy.data.objects[name].active_material.node_tree.nodes if n.type == "TEX_IMAGE")
        assert converted_color_name != source_color_name
        assert tuple(bpy.data.images[converted_color_name].size) == (64, 128)
        assert tuple(bpy.data.images[source_color_name].size) == (64, 64)
        np.testing.assert_array_equal(image_pixels(bpy.data.images[source_color_name]), original_pixels)
        converted_pixels = image_pixels(bpy.data.images[converted_color_name]).copy()
        assert not BakeMesh.poll(bpy.context)
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert len(bpy.data.objects[name].modifiers) == len(names) + 1
        assert bpy.data.objects[name]["o_image_object"] is True
        assert bpy.data.objects[name].data.name == mesh_name
        assert tuple(bpy.data.images[source_color_name].size) == (64, 64)
        np.testing.assert_array_equal(image_pixels(bpy.data.images[source_color_name]), original_pixels)
        assert next(n.image.name for n in bpy.data.objects[name].active_material.node_tree.nodes if n.type == "TEX_IMAGE") == source_color_name
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert [m.name for m in bpy.data.objects[name].modifiers] == names
        assert bpy.data.objects[name].modifiers[1].node_group.name == group_name
        assert "o_image_object" not in bpy.data.objects[name]
        assert tuple(bpy.data.images[converted_color_name].size) == (64, 128)
        np.testing.assert_array_equal(image_pixels(bpy.data.images[converted_color_name]), converted_pixels)
        np.testing.assert_array_equal(image_pixels(bpy.data.images[source_color_name]), original_pixels)
        assert bpy.data.objects[other_name].active_material.name == material_name
        assert not set(bpy.data.objects[name].data.attributes.keys()) & PROTOCOL_ATTRIBUTES
    finally:
        bpy.utils.unregister_class(BakeMesh)


@pytest.mark.parametrize("float_color", [False, True])
def test_packed_static_images_survive_library_reload(cutout, tmp_path, float_color):
    from anyimage.common.image import image_pixels

    if not float_color:
        color = bpy.data.images.new("Byte Color", width=13, height=9, alpha=True)
        color.colorspace_settings.name = "sRGB"
        color.pixels.foreach_set(np.linspace(0, 1, 13 * 9 * 4, dtype=np.float32))
        next(n for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE").image = color
    trailing = add_post_bake_modifiers(cutout)
    modifier_names = [m.name for m in trailing]
    modifier_states = [(m.show_viewport, m.show_render) for m in trailing]
    node_inputs = modifier_inputs(trailing[1])
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    positions, faces = mesh_geometry(cutout.data)
    images = [n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    expected = {i.name: (image_pixels(i), i.colorspace_settings.name, i.alpha_mode, i.is_float) for i in images}
    library = tmp_path / "static.blend"
    bpy.data.libraries.write(str(library), {cutout})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(library)) as (available, loaded):
        loaded.objects = available.objects
    obj = loaded.objects[0]
    assert [m.name for m in obj.modifiers] == modifier_names
    assert [(m.show_viewport, m.show_render) for m in obj.modifiers] == modifier_states
    assert modifier_inputs(obj.modifiers[1]) == node_inputs
    assert obj.animation_data.action is not None
    assert [(d.data_path, d.driver.expression) for d in obj.animation_data.drivers] == [
        ('modifiers["User displacement"].mid_level', "0"),
    ]
    np.testing.assert_array_equal(mesh_geometry(obj.data)[0], positions)
    assert mesh_geometry(obj.data)[1] == faces
    assert not set(obj.data.attributes.keys()) & PROTOCOL_ATTRIBUTES
    for node in obj.active_material.node_tree.nodes:
        if node.type != "TEX_IMAGE":
            continue
        image = node.image
        pixels, space, alpha, is_float = expected[image.name]
        assert image.packed_file and image.is_float == is_float
        assert image.colorspace_settings.name == space and image.alpha_mode == alpha
        np.testing.assert_array_equal(image_pixels(image), pixels)


@pytest.mark.parametrize("packed,file_format,extension", [(False, "PNG", "png"), (True, "OPEN_EXR", "exr")])
def test_disk_normal_is_replaced_and_packed_in_place(cutout, tmp_path, monkeypatch, packed, file_format, extension):
    from anyimage.operators.bake_mesh import materialization

    layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
    node = layer.inputs["Normal Texture"].links[0].from_node
    path = tmp_path / f"normal.{extension}"
    node.image.file_format = file_format
    node.image.filepath_raw = str(path)
    node.image.save()
    node.image = bpy.data.images.load(str(path), check_existing=False)
    node.image.colorspace_settings.name = "Non-Color"
    image = node.image
    if packed:
        image.pack()
    identity, name = image.as_pointer(), image.name
    disk_content = path.read_bytes()
    bake = materialization.bake_material_output
    expected = None

    def capture_bake(*args):
        nonlocal expected
        result = bake(*args)
        if args[3] == "Normal":
            expected = image_pixels(result).copy()
        return result

    monkeypatch.setattr(materialization, "bake_material_output", capture_bake)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    assert node.image.as_pointer() == identity and image.name == name
    assert image.filepath_raw == str(path) and path.read_bytes() == disk_content
    assert tuple(image.size) == (64, 128) and image.packed_file and image.is_float
    np.testing.assert_allclose(image_pixels(image), expected, atol=1 / 255)
    pixels = image_pixels(image).copy()
    library = tmp_path / "converted.blend"
    bpy.data.libraries.write(str(library), {cutout})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(library)) as (available, loaded):
        loaded.objects = available.objects
    image = bpy.data.images[name]
    assert tuple(image.size) == (64, 128) and image.packed_file and image.is_float
    np.testing.assert_array_equal(image_pixels(image), pixels)


def test_single_region_without_normal_or_bump_preserves_user_attributes(cutout):
    modifier = cutout.modifiers[0]
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"), 0)
    cutout.data.attributes.new("o_user_data", "FLOAT", "POINT")
    extra = cutout.data.uv_layers.new(name="UserUV")
    extra.data.foreach_set("uv", np.full(len(cutout.data.loops) * 2, .25, dtype=np.float32))
    nodes = cutout.active_material.node_tree.nodes
    layer = next(n for n in nodes if n.type == "GROUP")
    layer.inputs["Normal Scale"].default_value = .37
    layer.inputs["Bump Scale"].default_value = 0
    nodes.remove(layer.inputs["Normal Texture"].links[0].from_node)
    cutout.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    result = materialize_mesh_and_textures(bpy.context, cutout)
    assert "o_user_data" in result.attributes
    assert "UserUV" in result.uv_layers
    assert all(tuple(item.uv) == (.25, .25) for item in result.uv_layers["UserUV"].data)
    images = [n.image for n in result.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"]
    assert len(images) == 2 and all(tuple(image.size) == (64, 64) for image in images)
    assert not any(n.type == "GROUP" for n in result.materials[0].node_tree.nodes)
    assert any(n.type == "NEW_GEOMETRY" for n in result.materials[0].node_tree.nodes)


@pytest.mark.parametrize("failure", ["bake_material_output", "create_normalized_color_image"])
def test_bake_failure_keeps_source_and_cleans_resources(cutout, monkeypatch, failure):
    from anyimage.operators.bake_mesh import materialization

    trailing = add_post_bake_modifiers(cutout)
    states = [(m.show_viewport, m.show_render) for m in trailing]
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))
    source = cutout.data
    material = cutout.active_material
    images = [n.image for n in material.node_tree.nodes if n.type == "TEX_IMAGE"]
    def fail(*args, **kwargs):
        raise RuntimeError("Injected bake failure")
    monkeypatch.setattr(materialization, failure, fail)
    with pytest.raises(RuntimeError, match="Injected"):
        materialize_mesh_and_textures(bpy.context, cutout)
    assert cutout.data == source and tuple(cutout.modifiers)[1:] == trailing
    assert [(m.show_viewport, m.show_render) for m in trailing] == states
    assert cutout["o_image_object"] is True
    assert cutout.active_material == material
    assert images == [n.image for n in material.node_tree.nodes if n.type == "TEX_IMAGE"]
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))


def test_mesh_evaluation_failure_restores_subsequent_modifiers(cutout):
    trailing = add_post_bake_modifiers(cutout)
    visibility = trailing[0].driver_add("show_viewport")
    visibility.driver.expression = "True"
    states = [(m.show_viewport, m.show_render) for m in trailing]
    source = cutout.data
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))

    def fail():
        assert all(not m.show_viewport for m in trailing)
        raise RuntimeError("Injected evaluation failure")

    context = SimpleNamespace(object=cutout, view_layer=bpy.context.view_layer, evaluated_depsgraph_get=fail)
    operator = SimpleNamespace(report=Mock())
    assert BakeMesh.execute(operator, context) == {"CANCELLED"}
    operator.report.assert_called_once_with({"ERROR"}, "Injected evaluation failure")
    assert cutout.data == source and tuple(cutout.modifiers)[1:] == trailing
    assert [(m.show_viewport, m.show_render) for m in trailing] == states
    assert not visibility.mute
    assert cutout["o_image_object"] is True
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))


@pytest.mark.parametrize("packed,shared_color", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("byte_normal", [False, True])
def test_image_write_failure_restores_both_images(cutout, monkeypatch, packed, shared_color, byte_normal):
    from anyimage.operators.bake_mesh import materialization

    trailing = add_post_bake_modifiers(cutout)
    states = [(m.show_viewport, m.show_render) for m in trailing]
    source = cutout.data
    if byte_normal:
        layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
        texture = layer.inputs["Normal Texture"].links[0].from_node
        image = bpy.data.images.new("Byte normal", width=64, height=64)
        image.colorspace_settings.name = "Non-Color"
        image.pixels.foreach_set(image_pixels(texture.image))
        texture.image = image
    images = [n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    if shared_color:
        other_material = bpy.data.materials.new("Other Color user")
        other_material.use_nodes = True
        other_material.node_tree.nodes.new("ShaderNodeTexImage").image = images[0]
    color_pixels = image_pixels(images[0]).reshape(-1, 4)
    color_pixels[:, 3] = np.resize([0, .25, .5, 1], len(color_pixels))
    images[0].colorspace_settings.name = "Linear Rec.709"
    images[0].pixels.foreach_set(color_pixels.ravel())
    images[0].update()
    if packed:
        for image in images:
            if not image.packed_file:
                image.pack()
    precision = [image.is_float for image in images]
    pixels = [image_pixels(image).copy() for image in images]
    contents = [image_content_state(image) for image in images]
    identities = {image.name: image.as_pointer() for image in bpy.data.images}
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.scenes))
    layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Object Space"].default_value = True
    tree = cutout.active_material.node_tree
    node_ids = {n.as_pointer() for n in tree.nodes}
    connections = {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    replace = materialization.replace_image_content

    def fail_second_write(image, result):
        replace(image, result)
        if image == images[-1]:
            raise RuntimeError("Injected image write failure")

    monkeypatch.setattr(materialization, "replace_image_content", fail_second_write)
    with pytest.raises(RuntimeError, match="Injected image write"):
        materialize_mesh_and_textures(bpy.context, cutout)
    assert node_ids == {n.as_pointer() for n in tree.nodes}
    assert connections == {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    assert layer.inputs["Object Space"].default_value is True
    assert cutout.data == source and tuple(cutout.modifiers)[1:] == trailing
    assert [(m.show_viewport, m.show_render) for m in trailing] == states
    assert cutout["o_image_object"] is True
    assert {image.name: image.as_pointer() for image in bpy.data.images} == identities
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.scenes))
    assert [image.is_float for image in images] == precision
    for image, original, expected in zip(images, contents, pixels):
        assert tuple(image.size) == original["size"], (image.name, image.source, image.filepath_raw, original["source"], original["filepath"], image.packed_file is not None)
        np.testing.assert_array_equal(image_pixels(image), expected)
        actual = image_content_state(image)
        for field in ("size", "packed", "source", "filepath", "colorspace", "alpha_mode"):
            assert actual[field] == original[field]


@pytest.mark.parametrize("bump", [0, -10])
def test_conversion_preserves_normalized_fixed_light_appearance(cutout, tmp_path, bump):
    layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Bump Scale"].default_value = bump
    layer.inputs["Normal Scale"].default_value = .6
    color = layer.inputs["Color Texture"].links[0].from_node
    color.image = color_images.create_normalized_color_image(color.image)
    before = render_material(cutout, tmp_path / "lit-before.exr", (0, -1, 0), lighting=True)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    after = render_material(cutout, tmp_path / "lit-after.exr", (0, -1, 0), lighting=True)
    from scipy.ndimage import binary_erosion
    visible = binary_erosion(before[..., :3].max(axis=-1) > .01, iterations=4)
    differences = np.linalg.norm(before[visible, :3] - after[visible, :3], axis=-1)
    assert len(differences)
    assert np.quantile(differences, .95) < .06, np.quantile(differences, [.5, .95, 1])


def test_color_tiles_preserve_hdr_alpha_and_transparent_rgb(cutout):
    from anyimage.operators.bake_mesh.textures import build_color_tiles
    from anyimage.common.image import image_pixels

    image = next(n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE")
    pixels = image_pixels(image).reshape(64, 64, 4)
    pixels[:, :32, 3] = 0
    pixels[:, 32:, 3] = .25
    pixels[..., 2] = -.5
    image.pixels.foreach_set(pixels.ravel())
    result = build_color_tiles(image, ((1, 3), (0, 2)))
    np.testing.assert_array_equal(result[:64, :64], pixels[:, ::-1])
    np.testing.assert_array_equal(result[:64, 64:], pixels)
    np.testing.assert_array_equal(result[64:, :64], pixels)
    np.testing.assert_array_equal(result[64:, 64:], pixels[:, ::-1])

@pytest.mark.parametrize("regions,expected_tiles,offsets", [
    ((0,), ((0,),), ((0, 0),)),
    ((1,), ((1,),), ((0, 0),)),
    ((0, 1), ((1,), (0,)), ((0, 1), (0, 0))),
    ((0, 2), ((0, 2),), ((0, 0), (1, 0))),
    ((0, 1, 2, 3), ((1, 3), (0, 2)), ((0, 1), (0, 0), (1, 1), (1, 0))),
    ((0, 1, 3), ((1, 3), (0, None)), ((0, 1), (0, 0), (1, 0))),
])
def test_layout_preserves_surface_axes_and_composes_uv_flips(regions, expected_tiles, offsets):
    from anyimage.operators.bake_mesh.materialization import build_layout, SOURCE_UV, TARGET_UV
    mesh = bpy.data.meshes.new("Layout")
    try:
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)] * len(regions), [],
                        [(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(regions))])
        source = np.tile(np.array([[.1, .2], [.9, .3], [.4, .8]], dtype=np.float32), (len(regions), 1))
        mesh.uv_layers.new(name="UVMap").data.foreach_set("uv", source.ravel())
        mesh.attributes.new("o_image_region", "INT", "FACE").data.foreach_set("value", regions)
        tiles = build_layout(mesh)
        assert tiles == expected_tiles
        columns, rows = len(tiles[0]), len(tiles)
        actual = np.array([v.uv[:] for v in mesh.uv_layers[TARGET_UV].data])
        np.testing.assert_array_equal(np.array([v.uv[:] for v in mesh.uv_layers[SOURCE_UV].data]), source)
        for i in range(len(regions)):
            local = source[i * 3:i * 3 + 3].copy()
            if regions[i] in (1, 2):
                local[:, 0] = 1 - local[:, 0]
            expected = (local + offsets[i]) / (columns, rows)
            np.testing.assert_allclose(actual[i * 3:i * 3 + 3], expected)
    finally:
        bpy.data.meshes.remove(mesh)


@pytest.mark.parametrize("object_space", [False, True])
@pytest.mark.parametrize("strength", [0, .3, 2])
def test_conversion_bakes_strength_and_preserves_other_settings(cutout, tmp_path, object_space, strength):
    material = cutout.active_material
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Object Space"].default_value = object_space
    layer.inputs["Normal Scale"].default_value = strength
    layer.inputs["Bump Scale"].default_value = -.12
    shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["IOR"].default_value = 1.7
    layer = next(n for n in shader.id_data.nodes if n.type == "GROUP")
    shader.id_data.links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = .3
    before = render_material(cutout, tmp_path / "strength-before.exr", (0, -1, 0), with_uv_coverage=True)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    after = render_material(cutout, tmp_path / "strength-after.exr", (0, -1, 0), with_uv_coverage=True)
    from scipy.ndimage import binary_erosion
    visible = binary_erosion(before[1] == 1, iterations=3)
    errors = np.linalg.norm(before[0][visible, :3] - after[0][visible, :3], axis=-1)
    assert len(errors) and np.quantile(errors, .95) < .04
    assert cutout.active_material == material
    assert not any(n.type in {"GROUP", "BUMP"} for n in material.node_tree.nodes)
    normal = shader.inputs["Normal"].links[0].from_node
    assert normal.type == "NORMAL_MAP" and normal.space == "TANGENT"
    assert normal.inputs["Strength"].default_value == 1
    assert shader.inputs["IOR"].default_value == pytest.approx(1.7)
    assert shader.inputs["Emission Strength"].default_value == pytest.approx(.6)


def test_bake_context_setup_failure_releases_scene_and_object(cutout):
    from anyimage.common.bake import bake_context

    scene = bpy.context.window.scene
    counts = (len(bpy.data.scenes), len(bpy.data.objects))
    with pytest.raises(ValueError, match="sequence expected"):
        with bake_context(cutout.data, cutout.active_material, object()):
            pytest.fail("Invalid matrix must fail during setup")
    assert bpy.context.window.scene == scene
    assert counts == (len(bpy.data.scenes), len(bpy.data.objects))


@pytest.mark.parametrize("stage", ["allocation", "bake"])
@pytest.mark.parametrize("channel", ["Normal", "Roughness", "Alpha"])
def test_material_bake_failure_cleans_internal_resources(cutout, monkeypatch, stage, channel):
    from anyimage.operators.bake_mesh import materialization

    material = cutout.active_material.copy()
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    group = layer.node_tree
    counts = (len(bpy.data.images), len(bpy.data.node_groups), len(material.node_tree.nodes))
    fail = Mock(side_effect=RuntimeError("Injected internal failure"))
    proxy = SimpleNamespace(data=bpy.data, context=bpy.context, ops=bpy.ops)
    if stage == "allocation":
        proxy.data = SimpleNamespace(images=SimpleNamespace(new=fail), node_groups=bpy.data.node_groups)
    else:
        proxy.ops = SimpleNamespace(object=SimpleNamespace(bake=fail))
    monkeypatch.setattr(materialization, "bpy", proxy)
    try:
        with pytest.raises(RuntimeError, match="Injected internal"):
            materialization.bake_material_output(material, layer.name, (64, 128), channel)
        assert layer.node_tree == group
        assert counts == (len(bpy.data.images), len(bpy.data.node_groups), len(material.node_tree.nodes))
    finally:
        bpy.data.materials.remove(material)


@pytest.mark.parametrize("invalid_input", ["modifier", "linked_strength", "reserved_uv", "missing_uv", "shared_image", "constant_normal", "linked_alpha_fix", "custom_color"])
def test_unsupported_input_preserves_source_and_releases_resources(cutout, monkeypatch, invalid_input):
    from anyimage.operators.bake_mesh import materialization

    if invalid_input == "modifier":
        cutout.modifiers.new("User bevel", "BEVEL")
        cutout.modifiers.move(1, 0)
    elif invalid_input == "linked_strength":
        tree = cutout.active_material.node_tree
        layer = next(n for n in tree.nodes if n.type == "GROUP")
        tree.links.new(tree.nodes.new("ShaderNodeValue").outputs[0], layer.inputs["Normal Scale"])
    elif invalid_input in {"linked_alpha_fix", "custom_color"}:
        tree = cutout.active_material.node_tree
        layer = next(n for n in tree.nodes if n.type == "GROUP")
        if invalid_input == "linked_alpha_fix":
            tree.links.new(tree.nodes.new("ShaderNodeValue").outputs[0], layer.inputs["Alpha Scale"])
        else:
            group = layer.node_tree
            output = next(n for n in group.nodes if n.type == "GROUP_OUTPUT")
            source = next(n for n in group.nodes if n.type == "GROUP_INPUT")
            group.links.new(source.outputs["Normal Texture"], output.inputs["Color"])
    elif invalid_input == "reserved_uv":
        cutout.data.uv_layers.new(name=materialization.SOURCE_UV)
    elif invalid_input in {"shared_image", "constant_normal"}:
        tree = cutout.active_material.node_tree
        layer = next(n for n in tree.nodes if n.type == "GROUP")
        normal = layer.inputs["Normal Texture"].links[0].from_node
        if invalid_input == "shared_image":
            normal.image = layer.inputs["Color Texture"].links[0].from_node.image
        else:
            tree.nodes.remove(normal)
            layer.inputs["Object Space"].default_value = True
    else:
        cutout.data.uv_layers.remove(cutout.data.uv_layers["UVMap"])
    cutout.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    source = cutout.data
    material = cutout.active_material
    modifiers = list(cutout.modifiers)
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))
    bake = Mock(side_effect=AssertionError("Unsupported input must not reach baking"))
    monkeypatch.setattr(materialization, "bake_material_output", bake)
    with pytest.raises(ValueError):
        materialize_mesh_and_textures(bpy.context, cutout)
    bake.assert_not_called()
    assert cutout.data == source and cutout.active_material == material
    assert list(cutout.modifiers) == modifiers
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))


@pytest.mark.parametrize("bump", [-10, 10])
def test_bump_without_source_normal_creates_static_map(cutout, tmp_path, bump):
    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    tree.nodes.remove(layer.inputs["Normal Texture"].links[0].from_node)
    layer.inputs["Bump Scale"].default_value = bump
    before = render_material(cutout, tmp_path / "bump-before.exr", (0, -1, 0), with_uv_coverage=True)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    after = render_material(cutout, tmp_path / "bump-after.exr", (0, -1, 0), with_uv_coverage=True)
    from scipy.ndimage import binary_erosion
    visible = binary_erosion(before[1] == 1, iterations=3)
    errors = np.linalg.norm(before[0][visible, :3] - after[0][visible, :3], axis=-1)
    assert len(errors) and np.quantile(errors, .95) < .04
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    normal = shader.inputs["Normal"].links[0].from_node
    image = normal.inputs["Color"].links[0].from_node.image
    assert image.name.endswith("_normal.exr") and image.is_float and image.packed_file
    assert image.colorspace_settings.is_data and tuple(image.size) == (64, 128)
    assert np.max(np.abs(image_pixels(image).reshape(-1, 4)[:, 0] - .5)) > .01


@pytest.mark.parametrize("color_space,is_float", [("Non-Color", True), ("sRGB", False), ("AgX Base sRGB", False)])
def test_flattened_outputs_preserve_original_shader_values_and_consumers(cutout, tmp_path, color_space, is_float):
    from scipy.ndimage import binary_erosion
    from anyimage.common.image import is_color_reference_candidate

    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    layer.inputs["Alpha Scale"].default_value = .7
    texture = layer.inputs["Color Texture"].links[0].from_node
    source = texture.image
    color = bpy.data.images.new("Shader input", width=64, height=64, alpha=True, float_buffer=is_float)
    color.colorspace_settings.name = color_space
    color.pixels.foreach_set(image_pixels(source))
    texture.image = color
    pixels = image_pixels(color).reshape(64, 64, 4)
    pixels[..., 3] = np.linspace(.5, 1, 64)[None, :]
    color.pixels.foreach_set(pixels.ravel())
    layer.inputs["Roughness Contrast"].default_value = .6
    extra = tree.nodes.new("ShaderNodeMath")
    extra.operation = "MULTIPLY"
    extra.inputs[1].default_value = .3
    tree.links.new(layer.outputs["Roughness"], extra.inputs[0])
    unrelated = tree.nodes.new("ShaderNodeValue")
    tree.links.new(unrelated.outputs[0], extra.inputs[1])
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    tree.links.new(extra.outputs[0], shader.inputs["Metallic"])
    unused = tree.nodes.new("ShaderNodeMath")
    unused_source = tree.nodes.new("ShaderNodeValue")
    tree.links.new(unused_source.outputs[0], unused.inputs[0])
    tree.links.new(layer.outputs["Color"], unused.inputs[1])
    unused_names = {unused.name, unused_source.name}
    shader.inputs["Emission Strength"].default_value = .7
    channels = ("Roughness", "Alpha", "Emission")
    before = {channel: render_material(cutout, tmp_path / f"{i}-before.exr", (0, -1, 0), channel=channel,
                                      with_uv_coverage=True) for i, channel in enumerate(channels)}
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    for i, channel in enumerate(channels):
        after = render_material(cutout, tmp_path / f"{i}-after.exr", (0, -1, 0), channel=channel)
        original, coverage = before[channel]
        visible = binary_erosion(coverage == 1, iterations=3)
        expected = original[visible, :3]
        if channel == "Roughness":
            expected = np.clip(expected, 0, 1)
        elif channel == "Emission":
            expected = np.maximum(expected, 0)
        errors = np.abs(expected - after[visible, :3])
        assert len(errors) and np.quantile(errors, .95) < .02, (channel, np.quantile(errors, .95))
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    roughness = shader.inputs["Roughness"].links[0].from_node
    assert unused_names.isdisjoint(tree.nodes.keys())
    assert shader.inputs["Metallic"].links[0].from_node == extra
    assert extra.inputs[0].links[0].from_node == roughness
    assert extra.inputs[1].links[0].from_node == unrelated and extra.operation == "MULTIPLY"
    assert not roughness.image.is_float and roughness.image.colorspace_settings.is_data
    assert bytes(roughness.image.packed_file.data).startswith(b"\x89PNG\r\n\x1a\n")
    assert roughness.image.packed_file and not is_color_reference_candidate(roughness.image)
    assert shader.inputs["Alpha"].links[0].from_node == shader.inputs["Base Color"].links[0].from_node
    assert not any(image.name.endswith("_alpha.png") for image in bpy.data.images)


@pytest.mark.parametrize("stage", ["Roughness", "Alpha", "Normal", "connections", "layout"])
def test_flattening_failure_restores_nodes_links_and_images(cutout, monkeypatch, stage):
    from anyimage.operators.bake_mesh import materialization, materials

    tree = cutout.active_material.node_tree
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Emission Strength"].default_value = 2
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))
    nodes = {n.as_pointer() for n in tree.nodes}
    positions = {n.name: (tuple(n.location), n.width) for n in tree.nodes}
    links = {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    images = [(n.image, image_pixels(n.image).copy()) for n in tree.nodes if n.type == "TEX_IMAGE"]
    source = cutout.data
    if stage in {"connections", "layout"}:
        target = "connect_static_outputs" if stage == "connections" else "arrange_material_textures"
        connect = getattr(materials, target)
        def fail(*args):
            connect(*args)
            raise RuntimeError("Injected connections failure")
        monkeypatch.setattr(materials, target, fail)
    else:
        bake = materialization.bake_material_output
        def fail(*args):
            if args[-1] == stage:
                raise RuntimeError("Injected channel failure")
            return bake(*args)
        monkeypatch.setattr(materialization, "bake_material_output", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        materialize_mesh_and_textures(bpy.context, cutout)
    assert cutout.data == source and cutout["o_image_object"]
    assert nodes == {n.as_pointer() for n in tree.nodes}
    assert positions == {n.name: (tuple(n.location), n.width) for n in tree.nodes}
    assert links == {(link.from_socket.as_pointer(), link.to_socket.as_pointer()) for link in tree.links}
    for image, pixels in images:
        np.testing.assert_array_equal(image_pixels(image), pixels)
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))


@pytest.mark.parametrize("emission_strength", [0, 1])
def test_unused_bake_outputs_skip_cycles(cutout, monkeypatch, emission_strength):
    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    for name in ("Normal", "Roughness", "Alpha"):
        for link in tuple(layer.outputs[name].links):
            tree.links.remove(link)
    from anyimage.operators.bake_mesh import materialization

    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    layer = next(n for n in shader.id_data.nodes if n.type == "GROUP")
    shader.id_data.links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = emission_strength
    monkeypatch.setattr(materialization, "bake_context", Mock(side_effect=AssertionError("Unexpected Cycles scene")))
    image_count = len(bpy.data.images)
    result = materialize_mesh_and_textures(bpy.context, cutout)
    assert len(bpy.data.images) == image_count + bool(emission_strength)
    assert not any(n.type in {"NORMAL_MAP", "GROUP"} for n in result.materials[0].node_tree.nodes)


@pytest.mark.parametrize("strength", [0, .5, 1, 2])
@pytest.mark.parametrize("shared", [False, True])
def test_emission_uses_strength_and_independent_color_copy(cutout, tmp_path, strength, shared):
    tree = cutout.active_material.node_tree
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    layer = next(n for n in shader.id_data.nodes if n.type == "GROUP")
    shader.id_data.links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = strength
    other = None
    if shared:
        other = cutout.copy()
        bpy.context.collection.objects.link(other)
        other.hide_render = True
    original_color = image_pixels(layer.inputs["Color Texture"].links[0].from_node.image).reshape(64, 64, 4)
    expected_emission = np.concatenate([original_color[:, ::-1], original_color], axis=0).reshape(-1, 4)[:, :3]
    before = (render_material(cutout, tmp_path / "emission-before.exr", (0, -1, 0), channel="Emission")
              if strength == .5 and not shared else None)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    tree = cutout.active_material.node_tree
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    color = shader.inputs["Base Color"].links[0].from_node
    emission = shader.inputs["Emission Color"]
    assert shader.inputs["Emission Strength"].default_value == strength * 2
    copies = [n for n in tree.nodes if n.type == "TEX_IMAGE" and "_emissioncolor" in n.image.name]
    if strength == 0:
        assert not emission.is_linked and not copies
    else:
        assert len(copies) == 1 and emission.links[0].from_node == copies[0]
        image = copies[0].image
        assert image != color.image and tuple(image.size) == tuple(color.image.size)
        from anyimage.common.color_space import srgb_to_linear_rgb
        assert image.colorspace_settings.name == "sRGB" and not image.is_float
        assert bytes(image.packed_file.data).startswith(b"\x89PNG\r\n\x1a\n")
        restored = srgb_to_linear_rgb(image_pixels(image).reshape(-1, 4)[:, :3]) * 2
        np.testing.assert_allclose(restored, expected_emission, atol=.02)
        if before is not None:
            after = render_material(cutout, tmp_path / "emission-after.exr", (0, -1, 0), channel="Emission")
            np.testing.assert_allclose(after[..., :3], before[..., :3], atol=.02, rtol=.01)
        pixels = image_pixels(image)
        pixels[0] = .123
        image.pixels.foreach_set(pixels)
        assert image_pixels(image)[0] != image_pixels(color.image)[0]
    if other is not None:
        original = next(n for n in other.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        assert original.inputs["Emission Color"].is_linked
        assert original.inputs["Emission Color"].links[0].from_node.type == "GROUP"


def test_texture_rows_follow_principled_input_order(cutout):
    shader = next(n for n in cutout.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Emission Strength"].default_value = 2
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    ordered = []
    for name in ("Base Color", "Roughness", "Normal", "Emission Color"):
        source = shader.inputs[name].links[0].from_node
        if name == "Normal":
            source = source.inputs["Color"].links[0].from_node
        ordered.append(source)
    assert len({node.location.x for node in ordered}) == 1
    assert all(a.location.y - b.location.y >= 360 for a, b in zip(ordered, ordered[1:]))
    assert all(node.width == 240 for node in ordered)
    normal = shader.inputs["Normal"].links[0].from_node
    assert normal.location.y == ordered[2].location.y and normal.location.x > ordered[2].location.x


@pytest.mark.parametrize("strength", [0, .5, 1, 2])
def test_glb_export_preserves_specular_and_emission_policy(cutout, tmp_path, strength):
    import addon_utils
    import json
    import struct

    addon_utils.enable("io_scene_gltf2")
    shader = next(n for n in cutout.active_material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    layer = next(n for n in shader.id_data.nodes if n.type == "GROUP")
    shader.id_data.links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
    shader.inputs["Emission Strength"].default_value = strength
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    path = tmp_path / "baked.glb"
    assert bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", use_selection=True) == {"FINISHED"}
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    material = json.loads(data[20:20 + length])["materials"][0]
    assert "specularTexture" not in material.get("extensions", {}).get("KHR_materials_specular", {})
    if strength == 0:
        assert "emissiveTexture" not in material
        assert material.get("emissiveFactor", [0, 0, 0]) == [0, 0, 0]
    else:
        assert "emissiveTexture" in material
        factor = material.get("emissiveFactor", [0, 0, 0])
        multiplier = material.get("extensions", {}).get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 1)
        assert factor == pytest.approx([strength * 2 / multiplier] * 3)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.gltf(filepath=str(path)) == {"FINISHED"}
    shader = next(n for material in bpy.data.materials for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert shader.inputs["Emission Strength"].default_value == strength * 2


def test_bake_normalizes_inverse_color(cutout):
    from anyimage.common.color_space import normalize_color_rgba
    from anyimage.common.image import COLOR_NORMALIZED_PROPERTY, image_rgba

    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    image = bpy.data.images.new("Business color", width=64, height=64, alpha=True)
    rgba = np.ones((64, 64, 4), np.float32)
    rgba[..., 0] = np.linspace(.1, .9, 64)
    rgba[..., 1:3] = (.4, .6)
    image.pixels.foreach_set(rgba.ravel())
    color_images.configure_material_color_image(image, bpy.context.scene)
    assert image.colorspace_settings.name == "AgX Base sRGB"
    expected = normalize_color_rgba(color_images.decode_color_image(image, "AgX Base sRGB"))
    layer.inputs["Color Texture"].links[0].from_node.image = image
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    baked_color = shader.inputs["Base Color"].links[0].from_node.image
    assert baked_color.colorspace_settings.name == "sRGB" and not baked_color.is_float
    assert baked_color[COLOR_NORMALIZED_PROPERTY]
    assert bytes(baked_color.packed_file.data).startswith(b"\x89PNG\r\n\x1a\n")
    actual = image_rgba(baked_color)
    np.testing.assert_allclose(actual[..., :3], np.concatenate([expected, expected[:, ::-1]])[..., :3], atol=1 / 255)
    baked_color.reload()
    np.testing.assert_array_equal(image_rgba(baked_color), actual)


@pytest.mark.parametrize("scale,contrast", [(.5, -1), (1, .6)])
def test_scalar_bakes_preserve_layer_controls_in_both_engines(cutout, tmp_path, render_engine, scale, contrast):
    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    from PIL import Image

    path = tmp_path / "source.png"
    Image.new("RGBA", (32, 32), (26, 102, 230, 255)).save(path)
    image = bpy.data.images.load(str(path), check_existing=False)
    image.pack()
    layer.inputs["Color Texture"].links[0].from_node.image = image
    layer.inputs["Roughness Scale"].default_value = scale
    layer.inputs["Roughness Contrast"].default_value = contrast
    layer.inputs["Alpha Scale"].default_value = .7
    channels = ("Roughness", "Alpha")
    before = {channel: render_material(cutout, tmp_path / f"{channel}-before.exr", (0, -1, 0),
                                        channel=channel, engine=render_engine) for channel in channels}
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    for channel in channels:
        after = render_material(cutout, tmp_path / f"{channel}-after.exr", (0, -1, 0),
                                channel=channel, engine=render_engine)
        np.testing.assert_allclose(after[24:40, 24:40, :3], before[channel][24:40, 24:40, :3], atol=1 / 255)


@pytest.mark.parametrize("render_engine", ["EEVEE"], indirect=True)
@pytest.mark.parametrize("alpha_mode", ["PNG", "AgX", "STRAIGHT", "PREMUL"])
def test_eevee_transparent_surface_preserves_merged_alpha(cutout, tmp_path, alpha_mode, render_engine):
    from PIL import Image
    from anyimage.common.color_space import srgb_to_linear_rgb

    path = tmp_path / "transparent.png"
    Image.new("RGBA", (32, 32), (26, 102, 230, 153)).save(path)
    image = bpy.data.images.load(str(path), check_existing=False)
    if alpha_mode == "AgX":
        image.colorspace_settings.name = "AgX Base sRGB"
    elif alpha_mode != "PNG":
        rgba = image_pixels(image).reshape(-1, 4)
        rgba[:, :3] = srgb_to_linear_rgb(rgba[:, :3])
        if alpha_mode == "PREMUL":
            rgba[:, :3] *= rgba[:, 3:4]
        image = bpy.data.images.new("Linear color", width=32, height=32, alpha=True, float_buffer=True)
        image.colorspace_settings.name = "Linear Rec.709"
        image.alpha_mode = alpha_mode
        image.pixels.foreach_set(rgba.ravel())
    image.pack()
    tree = cutout.active_material.node_tree
    layer = next(n for n in tree.nodes if n.type == "GROUP")
    layer.inputs["Color Texture"].links[0].from_node.image = image
    layer.inputs["Alpha Scale"].default_value = .7
    if alpha_mode != "AgX":
        shader = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        tree.links.new(layer.outputs["Color"], shader.inputs["Emission Color"])
        shader.inputs["Emission Strength"].default_value = .7
    before = render_material(cutout, tmp_path / "lit-before.exr", (0, -1, 0),
                             channel="Alpha", engine=render_engine)
    cutout.data = materialize_mesh_and_textures(bpy.context, cutout)
    cutout.modifiers.clear()
    after = render_material(cutout, tmp_path / "lit-after.exr", (0, -1, 0),
                            channel="Alpha", engine=render_engine)
    # Eight-bit alpha quantization changes individual Eevee dither samples.
    error = np.abs(after[24:40, 24:40, :3] - before[24:40, 24:40, :3])
    assert np.quantile(error, .95) < .02
    assert error.max() < .04
