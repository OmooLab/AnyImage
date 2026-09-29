"""Verify static conversion of Plane, Depth Plane, Relief Plane and Panorama."""

import bpy
import numpy as np
import pytest
from unittest.mock import Mock
from types import SimpleNamespace

from anyimage.common.image import image_pixels
from anyimage.common.material import create_emission_material, create_image_material
from anyimage.common.object import modifier_input_identifier, set_modifier_input
from anyimage.operators.bake_mesh import BakeMesh
from anyimage.operators.bake_mesh import materialization
from nodes.groups.image_layer import build_image_layer_group
from tests.support.planes import create_surface
from tests.nodes.test_image_depth_panorama import panorama
from tests.anyimage.operators.test_mesh_materialization import render_normal


@pytest.fixture(params=["PLANE", "DEPTH", "RELIEF", "PANORAMA"])
def image_object(request):
    kind = request.param
    if kind == "PANORAMA":
        obj, _ = panorama(subdivide=2)
    else:
        obj, set_value, plane, *_ = create_surface("DEPTH" if kind == "PLANE" else kind)
        if kind == "PLANE":
            obj.modifiers[0].node_group = plane
        else:
            set_value("Depth Scale", .5)
            set_value("Subdivide", 4)
    build_image_layer_group()
    color = bpy.data.images.new("Color", width=128, height=64, alpha=True, float_buffer=True)
    color.colorspace_settings.name = "Non-Color"
    color.pixels.foreach_set(np.linspace(0, 1, 128 * 64 * 4, dtype=np.float32))
    normal = None
    if kind in {"DEPTH", "RELIEF"}:
        normal = bpy.data.images.new("Normal", width=128, height=64, alpha=True, float_buffer=True)
        normal.colorspace_settings.name = "Non-Color"
        normal.pixels.foreach_set(np.tile(np.array([.7, .6, .95, 1], np.float32), 128 * 64))
        normal.pack()
    if kind == "PANORAMA":
        material = create_emission_material(color, color, texture_extension="REPEAT")
    else:
        material = create_image_material(color, color, normal_image=normal,
                                         normal_space="OBJECT" if kind == "DEPTH" else "TANGENT")
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj["o_image_object"] = True
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    yield obj, kind, color, normal
    bpy.ops.wm.read_factory_settings(use_empty=True)


def test_four_conversions_keep_single_uv_and_existing_images(image_object, monkeypatch):
    obj, kind, color, normal = image_object
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    positions = np.array([v.co[:] for v in evaluated.vertices])
    uv = np.array([v.uv[:] for v in evaluated.uv_layers["UVMap"].data])
    faces = [tuple(p.vertices) for p in evaluated.polygons]
    material = obj.active_material
    images = {i.name: i.as_pointer() for i in bpy.data.images}
    color_pixels = image_pixels(color).copy()
    color_packed = bytes(color.packed_file.data)
    bake = Mock(wraps=materialization.bake_normal)
    monkeypatch.setattr(materialization, "bake_normal", bake)
    assert BakeMesh.poll(bpy.context)
    operator = SimpleNamespace(report=Mock())
    assert BakeMesh.execute(operator, bpy.context) == {"FINISHED"}
    assert not obj.modifiers and not BakeMesh.poll(bpy.context)
    assert obj.active_material == material
    remaining = {i.name: i.as_pointer() for i in bpy.data.images}
    assert all(images[name] == identity for name, identity in remaining.items())
    assert set(images) - set(remaining) == ({"Radial Depth"} if kind == "PANORAMA" else {"Camera"} if kind != "PLANE" else set())
    np.testing.assert_array_equal(image_pixels(color), color_pixels)
    assert bytes(color.packed_file.data) == color_packed
    np.testing.assert_array_equal([v.co[:] for v in obj.data.vertices], positions)
    np.testing.assert_array_equal([v.uv[:] for v in obj.data.uv_layers["UVMap"].data], uv)
    assert [tuple(p.vertices) for p in obj.data.polygons] == faces
    assert not set(obj.data.attributes.keys()) & materialization.PROTOCOL_ATTRIBUTES
    assert list(obj.data.uv_layers.keys()) == ["UVMap"]
    if normal is not None:
        bake.assert_called_once()
        assert tuple(normal.size) == (128, 64)
        layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
        assert layer.inputs["Object Space"].default_value is False
        assert layer.inputs["Normal Scale"].default_value == 1
    else:
        bake.assert_not_called()


@pytest.mark.parametrize("image_object", ["DEPTH", "RELIEF"], indirect=True)
@pytest.mark.parametrize("depth_scale", [0, .5, 1.5])
def test_single_region_normal_render_survives_attribute_cleanup(image_object, tmp_path, depth_scale):
    obj, kind, _, normal = image_object
    from scipy.ndimage import binary_erosion

    modifier = obj.modifiers[0]
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Depth Scale"), depth_scale)
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    layer = next(n for n in obj.active_material.node_tree.nodes if n.type == "GROUP")
    strength = .6 if kind == "RELIEF" else 1.0
    layer.inputs["Normal Scale"].default_value = strength
    before = render_normal(obj, tmp_path / "before.exr", (0, -1, 0), with_uv_coverage=True)
    obj.data = materialization.materialize_mesh_and_textures(bpy.context, obj)
    obj.modifiers.clear()
    after = render_normal(obj, tmp_path / "after.exr", (0, -1, 0), with_uv_coverage=True)
    np.testing.assert_array_equal(before[1], after[1])
    visible = binary_erosion(before[1] == 1, iterations=3)
    errors = np.linalg.norm(before[0][visible, :3] - after[0][visible, :3], axis=-1)
    assert len(errors) and np.quantile(errors, .95) < .04
    assert layer.inputs["Normal Scale"].default_value == pytest.approx(strength)
    assert not set(obj.data.attributes.keys()) & materialization.PROTOCOL_ATTRIBUTES


def test_four_conversions_support_undo_redo(image_object):
    obj, kind, color, normal = image_object
    name = obj.name
    image_names = [i.name for i in (color, normal) if i is not None]
    original_pixels = {name: image_pixels(bpy.data.images[name]).copy() for name in image_names}
    depth_name = "Radial Depth" if kind == "PANORAMA" else "Camera" if kind != "PLANE" else None
    if depth_name:
        bpy.data.images[depth_name].pack()
    bpy.context.preferences.edit.use_global_undo = True
    bpy.utils.register_class(BakeMesh)
    try:
        bpy.ops.ed.undo_push(message="Before conversion")
        assert bpy.ops.anyimage.bake_mesh("EXEC_DEFAULT", True) == {"FINISHED"}
        converted_pixels = {name: image_pixels(bpy.data.images[name]).copy() for name in image_names}
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert len(bpy.data.objects[name].modifiers) == 1
        if depth_name:
            assert depth_name in bpy.data.images
        for image_name in image_names:
            np.testing.assert_array_equal(image_pixels(bpy.data.images[image_name]), original_pixels[image_name])
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert not bpy.data.objects[name].modifiers
        if depth_name:
            assert depth_name not in bpy.data.images
        for image_name in image_names:
            np.testing.assert_array_equal(image_pixels(bpy.data.images[image_name]), converted_pixels[image_name])
    finally:
        bpy.utils.unregister_class(BakeMesh)


@pytest.mark.parametrize("image_object", ["DEPTH", "RELIEF", "PANORAMA"], indirect=True)
@pytest.mark.parametrize("user", ["none", "modifier", "material", "fake"])
def test_conversion_only_removes_unreferenced_depth(image_object, user, tmp_path):
    obj, kind, *_ = image_object
    depth_name = "Radial Depth" if kind == "PANORAMA" else "Camera"
    depth = bpy.data.images[depth_name]
    path = tmp_path / "depth.exr"
    depth.filepath_raw = str(path)
    depth.file_format = "OPEN_EXR"
    depth.save()
    depth.pack()
    disk_content = path.read_bytes()
    unrelated = bpy.data.images.new("Unrelated orphan", width=1, height=1)
    if user == "modifier":
        other = obj.copy()
        bpy.context.collection.objects.link(other)
    elif user == "material":
        obj.active_material.node_tree.nodes.new("ShaderNodeTexImage").image = depth
    elif user == "fake":
        depth.use_fake_user = True
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"FINISHED"}
    assert (depth_name in bpy.data.images) == (user != "none")
    assert unrelated.name in bpy.data.images
    assert path.read_bytes() == disk_content


@pytest.mark.parametrize("image_object", ["DEPTH", "RELIEF", "PANORAMA"], indirect=True)
def test_conversion_failure_keeps_depth(image_object, monkeypatch):
    from anyimage.operators.bake_mesh import operators

    obj, kind, *_ = image_object
    depth = bpy.data.images["Radial Depth" if kind == "PANORAMA" else "Camera"]
    source = obj.data
    identity = depth.as_pointer()
    monkeypatch.setattr(operators, "materialize_mesh_and_textures", Mock(side_effect=RuntimeError("Injected failure")))
    assert BakeMesh.execute(SimpleNamespace(report=Mock()), bpy.context) == {"CANCELLED"}
    assert depth.as_pointer() == identity and depth.users > 0
    assert obj.data == source and len(obj.modifiers) == 1
