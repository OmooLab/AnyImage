"""Verify the public panorama entry and transactional Blender result handling."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest
from PIL import Image
from mathutils import Matrix

from anyimage.operators.convert_to_panorama import operators, object as conversion
from server.geometry.depth_texture import write_float_exr
from anyimage.common.color_image import prepare_material_color_input, cleanup_material_color_input
from anyimage.common.image import image_content_signature


@pytest.mark.parametrize("size, expected", [
    ((32, 16), (0, 0, 32, 16)),
    ((40, 16), (4, 0, 36, 16)),
    ((30, 20), (0, 2, 30, 17)),
    ((31, 20), (0, 2, 30, 17)),
    ((35, 16), (1, 0, 33, 16)),
])
def test_panorama_crop_bounds(size, expected):
    assert operators.panorama_crop_bounds(*size) == expected


@pytest.mark.parametrize("size", [(0, 1), (1, 1), (2, 0), (-2, 1)])
def test_panorama_crop_bounds_rejects_unusable_dimensions(size):
    with pytest.raises(ValueError, match="at least 2 x 1 pixels"):
        operators.panorama_crop_bounds(*size)


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Current panorama", width=32, height=16, alpha=True)
    rgba = np.ones((16, 32, 4), np.float32)
    rgba[:8, :, 3] = 0
    rgba[8:12, :, 3] = 0.5
    image.pixels.foreach_set(rgba.ravel())
    obj = bpy.data.objects.new("Panorama Empty", None)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def test_entry_submits_current_alpha_preferences_and_cleans_cancelled_input(source, monkeypatch):
    submitted = {}
    def submit(**parameters):
        submitted.update(parameters)
        with Image.open(parameters["input_path"]) as image:
            alpha = np.asarray(image)[..., 3]
            assert not alpha[8:].any()
            assert np.all(abs(alpha[4:8].astype(float) - 128) <= 1)
        return {"CANCELLED"}
    monkeypatch.setattr(operators, "invoke_ai_setup_if_needed", lambda _operator: None)
    monkeypatch.setattr(operators, "addon_preferences", lambda _: SimpleNamespace(geometry_model="MOGE2_VITB", geometry_resolution_level=2))
    monkeypatch.setattr(operators, "configured_geometry_model", lambda _: "MOGE2_VITB_NORMAL")
    monkeypatch.setattr(operators, "configured_max_ai_input_size", lambda _: 1024)
    monkeypatch.setattr(operators, "bpy", SimpleNamespace(ops=SimpleNamespace(anyimage=SimpleNamespace(generate_panorama=submit))))
    operator = SimpleNamespace(report=Mock())
    assert operators.ConvertToPanorama.execute(operator, bpy.context) == {"CANCELLED"}
    assert submitted["model"] == "MOGE2_VITB_NORMAL" and submitted["resolution_level"] == 2
    assert submitted["max_input_size"] == 1024
    assert submitted["color_path"] == submitted["input_path"]
    operator.report.assert_not_called()
    from pathlib import Path
    assert not Path(submitted["input_path"]).exists()
    assert bpy.data.objects.get(source.name) == source


def test_entry_crops_arbitrary_aspect_before_submitting_and_warns(source, monkeypatch):
    source.data.scale(31, 20)
    source.data.pixels.foreach_set(np.ones((20, 31, 4), np.float32).ravel())
    submitted = {}

    def submit(**parameters):
        submitted.update(parameters)
        with Image.open(parameters["input_path"]) as image:
            assert image.size == (30, 15)
        with Image.open(parameters["color_path"]) as image:
            assert image.size == (30, 15)
        return {"CANCELLED"}

    monkeypatch.setattr(operators, "invoke_ai_setup_if_needed", lambda _operator: None)
    monkeypatch.setattr(operators, "addon_preferences", lambda _: SimpleNamespace(geometry_resolution_level=5))
    monkeypatch.setattr(operators, "configured_geometry_model", lambda _: "MOGE2_VITB_NORMAL")
    monkeypatch.setattr(operators, "configured_max_ai_input_size", lambda _: 1024)
    monkeypatch.setattr(operators, "bpy", SimpleNamespace(
        app=bpy.app,
        ops=SimpleNamespace(anyimage=SimpleNamespace(generate_panorama=submit))))
    operator = SimpleNamespace(report=Mock())

    assert operators.ConvertToPanorama.execute(operator, bpy.context) == {"CANCELLED"}
    operator.report.assert_called_once_with(
        {"WARNING"}, "Panorama input cropped from 31 x 20 to 30 x 15")


@pytest.mark.parametrize("image_source,size", [("MOVIE", (32, 16)), ("SEQUENCE", (32, 16)), ("FILE", (1, 32))])
def test_invalid_input_is_rejected_before_setup(image_source, size, monkeypatch):
    setup = Mock()
    monkeypatch.setattr(operators, "invoke_ai_setup_if_needed", setup)
    obj = SimpleNamespace(data=SimpleNamespace(source=image_source, size=size))
    assert operators.ConvertToPanorama.execute(SimpleNamespace(report=Mock()), SimpleNamespace(object=obj)) == {"CANCELLED"}
    setup.assert_not_called()


@pytest.fixture
def artifacts(tmp_path, source):
    rgba = np.ones((16, 32, 4), np.float32)
    rgba[..., :3] = 3
    write_float_exr(rgba, tmp_path / "depth.exr")
    (tmp_path / "depth.json").write_text(json.dumps({"projection": "equirectangular", "image_size": [32, 16]}))
    Image.new("RGB", (32, 16), (128, 128, 255)).save(tmp_path / "normal.png")
    result = SimpleNamespace(directory=tmp_path, file=lambda key: tmp_path / {"depth": "depth.exr", "depth_metadata": "depth.json", "object_normal": "normal.png"}[key])
    operator = SimpleNamespace(source_object_name=source.name, _source_object=source,
                               _source_image=source.data, _source_signature=image_content_signature(source.data),
                               color_path=str(prepare_material_color_input(source.data)))
    yield result, operator
    cleanup_material_color_input(operator.color_path)


def test_result_replaces_source_with_zero_rotation_and_object_normal_material(source, artifacts, monkeypatch):
    result, operator = artifacts
    from anyimage.common.node import load_node_group
    saved = load_node_group("O Depth Panorama")
    matrix = Matrix.Translation((2, -3, 4)) @ Matrix.Rotation(0.6, 4, "Y") @ Matrix.Diagonal((2, 3, 4, 1))
    source.matrix_world = matrix
    source.empty_image_offset = (0.3, -0.8)
    undo = Mock(return_value={"FINISHED"})
    monkeypatch.setattr(conversion, "bpy", SimpleNamespace(data=bpy.data, ops=SimpleNamespace(ed=SimpleNamespace(undo_push=undo))))
    obj = conversion.create_panorama_from_result(bpy.context, result, operator)
    assert obj["o_image_object"] is True
    assert obj.visible_shadow is False
    assert not obj.children
    assert "anyimage_mesh_shape" not in obj
    assert obj.modifiers[0].node_group == saved
    from anyimage.common.object import get_modifier_input, modifier_input_identifier
    assert get_modifier_input(obj.modifiers[0], modifier_input_identifier(saved, "Subdivide")) == 6
    assert get_modifier_input(obj.modifiers[0], modifier_input_identifier(saved, "Horizon Bend")) == pytest.approx(-0.1)
    assert saved.name == "O Depth Panorama"
    assert obj.name == operator.source_object_name and obj.type == "MESH"
    np.testing.assert_allclose(obj.location, matrix.translation, atol=1e-6)
    np.testing.assert_allclose(obj.scale, matrix.to_scale(), atol=1e-6)
    np.testing.assert_array_equal(obj.rotation_euler, (0, 0, 0))
    material = obj.data.materials[0]
    assert material.use_backface_culling is True
    assert material.use_backface_culling_shadow is True
    nodes = material.node_tree.nodes
    assert not any(n.bl_idname == "ShaderNodeUVMap" for n in nodes)
    layer = next(n for n in nodes if n.type == "GROUP")
    shader = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    assert layer.node_tree.name == "O Texture to Layer"
    assert layer.inputs["Object Space"].default_value
    assert shader.inputs["Emission Strength"].default_value == 1.0
    assert not shader.inputs["Emission Strength"].is_linked
    assert layer.inputs["Roughness Scale"].default_value == 1
    assert not any(n.type == "ATTRIBUTE" for n in nodes)
    assert not any(n.type in {"TEX_COORD", "VECT_MATH", "MATH"} for n in nodes)
    color = layer.inputs["Color Texture"].links[0].from_node.image
    world = bpy.context.scene.world
    environment = next(n for n in world.node_tree.nodes if n.type == "TEX_ENVIRONMENT")
    background = next(n for n in world.node_tree.nodes if n.type == "GROUP")
    assert environment.image == color
    assert background.node_tree.name == "O Background"
    assert background.inputs["Light"].links[0].from_node == environment
    assert not background.inputs["Color"].is_linked
    assert color.colorspace_settings.name == "AgX Base sRGB"
    assert color.alpha_mode == "STRAIGHT"
    normal = layer.inputs["Normal Texture"].links[0].from_node
    assert normal.image.colorspace_settings.is_data and normal.image.packed_file
    assert all(n.extension == "REPEAT" for n in nodes if n.type == "TEX_IMAGE")
    assert shader.inputs["Normal"].links[0].from_node == layer
    assert shader.inputs["Emission Color"].links[0].from_socket == layer.outputs["Emission"]
    assert bpy.context.view_layer.objects.active == obj
    assert all(image.packed_file for image in bpy.data.images if image.name.endswith(("_color.png", "_depth.exr", "_normal.png")))
    graph = bpy.context.evaluated_depsgraph_get()
    mesh = obj.evaluated_get(graph).to_mesh()
    try:
        assert len(mesh.polygons) == 6 * 4 ** 7 and mesh.uv_layers.active
        assert mesh.materials[0].original == material
        assert all(face.material_index == 0 and face.use_smooth for face in mesh.polygons)
    finally:
        obj.evaluated_get(graph).to_mesh_clear()
    undo.assert_called_once_with(message="Convert to Panorama")


@pytest.mark.parametrize("shared", [False, True])
def test_panorama_preserves_hdr_pixels_color_space_and_alpha(source, artifacts, monkeypatch, shared):
    result, operator = artifacts
    hdr = bpy.data.images.new("Original HDR", width=32, height=16, alpha=True, float_buffer=True)
    hdr.alpha_mode = "PREMUL"
    rgba = np.ones((16, 32, 4), np.float32)
    rgba[..., :3] = (4.0, 2.0, 0.5)
    rgba[..., 3] = 0.5
    hdr.pixels.foreach_set(rgba.ravel())
    source.data = hdr
    operator._source_image = hdr
    operator._source_signature = image_content_signature(hdr)
    cleanup_material_color_input(operator.color_path)
    operator.color_path = str(prepare_material_color_input(hdr))
    if shared:
        other = source.copy()
        bpy.context.collection.objects.link(other)
    original_space, original_alpha = hdr.colorspace_settings.name, hdr.alpha_mode
    monkeypatch.setattr(conversion, "bpy", SimpleNamespace(data=bpy.data, ops=SimpleNamespace(ed=SimpleNamespace(undo_push=lambda **kw: {"FINISHED"})) ))
    obj = conversion.create_panorama_from_result(bpy.context, result, operator)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    assert color != hdr
    assert color.is_float and color.packed_file
    assert (color.colorspace_settings.name, color.alpha_mode) == (original_space, original_alpha)
    np.testing.assert_allclose(color.pixels[:], rgba.ravel(), atol=1e-6)
    assert (hdr.colorspace_settings.name, hdr.alpha_mode) == (original_space, original_alpha)
    library = result.directory / "hdr-copy.blend"
    bpy.data.libraries.write(str(library), {color})
    with bpy.data.libraries.load(str(library)) as (saved, loaded):
        loaded.images = saved.images
    restored = loaded.images[0]
    assert restored.is_float
    assert (restored.colorspace_settings.name, restored.alpha_mode) == (original_space, original_alpha)
    np.testing.assert_allclose(restored.pixels[:], rgba.ravel(), atol=1e-6)


@pytest.mark.parametrize("failure", ["modifier", "normal_size", "depth_size", "stale", "replaced_image", "world", "finalize"])
def test_failed_response_keeps_source_and_cleans_owned_data(source, artifacts, monkeypatch, failure):
    result, operator = artifacts
    previous_world = bpy.data.worlds.new("Existing World")
    bpy.context.scene.world = previous_world
    before = {name: set(getattr(bpy.data, name)) for name in ("images", "objects", "meshes", "materials", "worlds")}
    if failure == "normal_size":
        Image.new("RGB", (4, 4)).save(result.file("object_normal"))
    elif failure == "modifier":
        monkeypatch.setattr(conversion, "set_modifier_input", Mock(side_effect=RuntimeError("Failed modifier")))
    elif failure == "finalize":
        monkeypatch.setattr(conversion, "finalize_object_result", Mock(side_effect=RuntimeError("Failed finalize")))
    elif failure == "world":
        from anyimage.operators.convert_to_panorama import world
        monkeypatch.setattr(world, "load_node_group", Mock(side_effect=RuntimeError("Failed world")))
    elif failure == "stale":
        operator._source_object = object()
    elif failure == "replaced_image":
        operator._source_image = object()
    else:
        (result.directory / "depth.json").write_text(json.dumps({"projection": "equirectangular", "image_size": [16, 8]}))
    with pytest.raises((RuntimeError, ValueError)):
        conversion.create_panorama_from_result(bpy.context, result, operator)
    for name, values in before.items():
        assert set(getattr(bpy.data, name)) == values
    assert bpy.context.scene.world == previous_world


def test_panorama_conversion_undo_restores_empty(source, artifacts):
    result, operator = artifacts
    name = source.name
    image_name = source.data.name
    original_space, original_alpha = source.data.colorspace_settings.name, source.data.alpha_mode
    bpy.context.scene.world = bpy.data.worlds.new("Original World")
    bpy.context.preferences.edit.use_global_undo = True
    def execute(self, context):
        conversion.create_panorama_from_result(context, result, operator)
        return {"FINISHED"}
    with patch.object(operators.GeneratePanorama, "execute", execute):
        bpy.utils.register_class(operators.GeneratePanorama)
        try:
            bpy.ops.ed.undo_push(message="Before Panorama")
            assert bpy.ops.anyimage.generate_panorama("EXEC_DEFAULT") == {"FINISHED"}
            assert bpy.data.objects[name].type == "MESH"
            world_name = bpy.context.scene.world.name
            assert world_name != "Original World"
            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert bpy.context.scene.world.name == "Original World"
            assert bpy.data.objects[name].type == "EMPTY"
            assert (bpy.data.images[image_name].colorspace_settings.name,
                    bpy.data.images[image_name].alpha_mode) == (original_space, original_alpha)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            assert bpy.context.scene.world.name == world_name
            assert bpy.data.objects[name].type == "MESH"
            assert not bpy.data.objects[name].children
        finally:
            bpy.utils.unregister_class(operators.GeneratePanorama)


def test_depth_mask_default_preserves_background_dome(source, artifacts, monkeypatch):
    from anyimage.common.object import get_modifier_input, modifier_input_identifier

    rgba = np.ones((16, 32, 4), np.float32)
    rgba[..., :3] = 3
    rgba[:8, :, 3] = 0
    write_float_exr(rgba, artifacts[0].file("depth"))
    monkeypatch.setattr(conversion, "bpy", SimpleNamespace(
        data=bpy.data, ops=SimpleNamespace(ed=SimpleNamespace(undo_push=lambda **kw: {"FINISHED"})) ))
    obj = conversion.create_panorama_from_result(bpy.context, *artifacts)
    modifier = obj.modifiers[0]
    identifier = modifier_input_identifier(modifier.node_group, "Depth Mask")
    assert get_modifier_input(modifier, identifier) is False
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        positions = np.empty(len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", positions)
        radii = np.linalg.norm(positions.reshape(-1, 3), axis=1)
        assert np.isclose(radii, 3, atol=0.01).any()
        assert np.isclose(radii, 200, atol=0.01).any()
    finally:
        evaluated.to_mesh_clear()
