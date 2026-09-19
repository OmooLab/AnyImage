"""Verify conversion ownership, source recovery, and persistent color data."""

from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import image as images, material
from anyimage.common.color_image import prepare_material_color_input, cleanup_material_color_input
from anyimage.operators.convert_to_plane import operators, object as conversion, image_plane


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Source.png", width=2, height=1, alpha=True)
    image.pixels.foreach_set([0.2, 0.4, 0.8, 0.25, 0.6, 0.3, 0.1, 0])
    obj = bpy.data.objects.new("Source", None)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    yield obj
    bpy.ops.wm.read_factory_settings(use_empty=True)


def share_image(source, sharing):
    if sharing in {"visible", "hidden", "other_scene", "same_path"}:
        other = source.copy()
        if sharing == "same_path":
            source.data.filepath_raw = "//source.png"
            other.data = source.data.copy()
        collection = bpy.context.collection
        if sharing == "other_scene":
            collection = bpy.data.scenes.new("Other scene").collection
        collection.objects.link(other)
        other.hide_viewport = sharing == "hidden"
    elif sharing == "material":
        existing = bpy.data.materials.new("Existing")
        existing.use_nodes = True
        existing.node_tree.nodes.new("ShaderNodeTexImage").image = source.data


def run_conversion(source, entry, monkeypatch):
    if entry == "PLANE":
        operators.ConvertToPlane.execute(SimpleNamespace(mesh_detail=0), bpy.context)
    else:
        metadata = {"image_size": (2, 1),
                    "intrinsics": ((2, 0, 1), (0, 2, 0.5), (0, 0, 1))}
        monkeypatch.setattr(conversion, "load_depth_metadata", lambda _: metadata)
        def load_depth(*_):
            image = bpy.data.images.new("Depth", width=2, height=1, float_buffer=True)
            image.colorspace_settings.name = "Non-Color"
            image.pixels.foreach_set(np.ones(8, dtype=np.float32))
            return image
        monkeypatch.setattr(conversion, "load_depth_result_image", load_depth)
        monkeypatch.setattr(conversion, "load_normal_result_image", load_depth)
        monkeypatch.setattr(conversion, "bpy", SimpleNamespace(data=bpy.data,
            ops=SimpleNamespace(ed=SimpleNamespace(undo_push=lambda **_: {"FINISHED"}))))
        path = prepare_material_color_input(source.data)
        try:
            conversion.create_depth_plane_from_result(bpy.context, SimpleNamespace(file=lambda key: key),
                SimpleNamespace(source_object_name=source.name, source_identity=str(source.as_pointer()),
                                image_identity=str(source.data.as_pointer()), color_path=str(path), plane_type=entry, mesh_detail=0))
        finally:
            cleanup_material_color_input(path)
    return bpy.context.object


@pytest.mark.parametrize("entry,sharing", [
    ("PLANE", "none"),
    ("PLANE", "material"),
    ("DEPTH", "visible"),
])
def test_conversion_selects_source_by_empty_identity(source, monkeypatch, entry, sharing):
    share_image(source, sharing)
    original = source.data
    before = images.image_pixels(original)
    name, path = original.name, original.filepath_raw
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: False)
    obj = run_conversion(source, entry, monkeypatch)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    assert color != original
    assert color.name == "Source_color.png"
    assert color.filepath_raw != original.filepath_raw
    assert original.name == name and original.filepath_raw == path
    assert color.colorspace_settings.name == "sRGB" and color.alpha_mode == "PREMUL"
    assert original.alpha_mode == "STRAIGHT"
    np.testing.assert_array_equal(images.image_pixels(original), before)
    np.testing.assert_allclose(images.image_pixels(color), before, atol=1 / 255)
    if sharing == "material":
        existing = bpy.data.materials["Existing"]
        assert next(n.image for n in existing.node_tree.nodes if n.type == "TEX_IMAGE") == original


@pytest.mark.parametrize("shared,failure,entry", [
    (False, "material", "PLANE"),
    (True, "modifier", "DEPTH"),
    (False, "finalize", "PLANE"),
])
def test_conversion_failure_restores_image_and_releases_resources(source, monkeypatch, shared, failure, entry):
    if shared:
        share_image(source, "visible")
    source.data.pack()
    source.data.pixels[0] = 0.75
    original = source.data
    state = images.image_content_state(original)
    before = {name: set(getattr(bpy.data, name)) for name in ("images", "objects", "meshes", "materials")}
    def fail(*args, **kwargs):
        raise RuntimeError("Conversion failed")
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: True)
    if failure == "material":
        monkeypatch.setattr(material, "material_node_group", fail)
    elif failure == "finalize":
        monkeypatch.setattr(conversion, "finalize_object_result", fail)
    elif entry == "PLANE":
        monkeypatch.setattr(image_plane, "add_image_plane_processing", fail)
    else:
        monkeypatch.setattr(conversion, "set_modifier_input", fail)
    with pytest.raises(RuntimeError, match="Conversion failed"):
        run_conversion(source, entry, monkeypatch)
    for name, values in before.items():
        assert set(getattr(bpy.data, name)) == values
    assert source.data == original
    assert (original.colorspace_settings.name, original.alpha_mode) == (state["colorspace"], state["alpha_mode"])
    assert bytes(original.packed_file.data) == state["packed"]
    np.testing.assert_array_equal(original.pixels[:], state["pixels"])


@pytest.mark.parametrize("shared,kind", [(False, "generated"), (True, "file")])
def test_conversion_pixels_survive_library_reload(source, tmp_path, monkeypatch, kind, shared):
    if kind in {"file", "dirty"}:
        path = tmp_path / "source.png"
        Image.fromarray(np.array([[[51, 102, 204, 64], [153, 76, 25, 0]]], np.uint8)).save(path)
        source.data = bpy.data.images.load(str(path))
        if kind == "dirty":
            source.data.pixels[0] = 0.8
    elif kind == "packed":
        source.data.pack()
        source.data.reload()
    if shared:
        share_image(source, "visible")
    expected = images.image_pixels(source.data)
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: True)
    obj = run_conversion(source, "PLANE", monkeypatch)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    library = tmp_path / "converted.blend"
    bpy.data.libraries.write(str(library), {color})
    with bpy.data.libraries.load(str(library)) as (saved, loaded):
        loaded.images = saved.images
    restored = loaded.images[0]
    assert (restored.colorspace_settings.name, restored.alpha_mode) == (color.colorspace_settings.name, color.alpha_mode)
    np.testing.assert_allclose(images.image_pixels(restored), expected, atol=1 / 255)


@pytest.mark.parametrize("entry", ["DEPTH", "RELIEF"])
def test_depth_result_rejects_replaced_source_image(source, entry):
    operator = SimpleNamespace(source_object_name=source.name, source_identity=str(source.as_pointer()),
                               image_identity=str(source.data.as_pointer()), plane_type=entry)
    source.data = source.data.copy()
    with pytest.raises(ValueError, match="source image has changed"):
        conversion.create_depth_plane_from_result(bpy.context, None, operator)


@pytest.mark.parametrize("shared", [False, True])
def test_plane_undo_redo_restores_image_configuration(source, monkeypatch, shared):
    if shared:
        share_image(source, "visible")
    original_name = source.data.name
    expected = images.image_pixels(source.data)
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: False)
    bpy.context.preferences.edit.use_global_undo = True
    bpy.utils.register_class(operators.ConvertToPlane)
    try:
        bpy.ops.ed.undo_push(message="Before Plane")
        assert bpy.ops.anyimage.convert_to_plane("EXEC_DEFAULT", True) == {"FINISHED"}
        color_name = "Source_color.png"
        assert bpy.data.images[color_name].alpha_mode == "PREMUL"
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert bpy.data.objects["Source"].type == "EMPTY"
        assert bpy.data.images[original_name].alpha_mode == "STRAIGHT"
        np.testing.assert_allclose(images.image_pixels(bpy.data.images[original_name]), expected, atol=1 / 255)
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert bpy.data.objects["Source"].type == "MESH"
        assert bpy.data.images[color_name].alpha_mode == "PREMUL"
    finally:
        bpy.utils.unregister_class(operators.ConvertToPlane)
