"""Verify conversion ownership, source recovery, and persistent color data."""

from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import image as images, material
from anyimage.operators import convert_to_plane as operators
from anyimage.operators import depth_plane as conversion


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
    if sharing == "visible":
        bpy.context.collection.objects.link(source.copy())
    elif sharing == "material":
        existing = bpy.data.materials.new("Existing")
        existing.use_nodes = True
        existing.node_tree.nodes.new("ShaderNodeTexImage").image = source.data


def run_conversion(source, entry, monkeypatch):
    if entry == "PLANE":
        operators.ConvertToPlane.execute(SimpleNamespace(), bpy.context)
    else:
        def load_depth(*_):
            image = bpy.data.images.new("Depth", width=2, height=1, float_buffer=True)
            image.colorspace_settings.name = "Non-Color"
            image.pixels.foreach_set(np.ones(8, dtype=np.float32))
            return image
        monkeypatch.setattr(conversion, "load_depth_result_image", load_depth)
        monkeypatch.setattr(conversion, "load_normal_result_image", load_depth)
        monkeypatch.setattr(conversion, "bpy", SimpleNamespace(data=bpy.data,
            ops=SimpleNamespace(ed=SimpleNamespace(undo_push=lambda **_: {"FINISHED"}))))
        operator = SimpleNamespace(_scene=bpy.context.scene, _source_object=source, _source_image=source.data,
                                   plane_type=entry, bl_label="Convert to Depth Plane", ready_message="Depth Plane is ready")
        monkeypatch.setattr(conversion, "geometry_job_parameters", lambda _: {})
        conversion.DepthPlaneJob.request(operator, bpy.context)
        try:
            conversion.DepthPlaneJob.response(
                operator, bpy.context, SimpleNamespace(file=lambda key: key, value={"intrinsics": [[2, 0, 1], [0, 2, 0.5], [0, 0, 1]]}),
            )
        finally:
            conversion.DepthPlaneJob.cleanup(operator)
    return bpy.context.object


@pytest.mark.parametrize("entry", ["PLANE", "DEPTH", "RELIEF"])
def test_conversion_requests_material_preview(source, monkeypatch, entry):
    calls = []
    module = operators if entry == "PLANE" else conversion
    monkeypatch.setattr(module, "apply_material_preview", calls.append)
    run_conversion(source, entry, monkeypatch)
    assert calls == [bpy.context]


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
    obj = run_conversion(source, entry, monkeypatch)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    assert color != original
    assert color.name == "Source_color.png"
    assert color.filepath_raw != original.filepath_raw
    assert original.name == name and original.filepath_raw == path
    assert color.colorspace_settings.name == "AgX Base sRGB" and color.alpha_mode == "STRAIGHT"
    assert original.alpha_mode == "STRAIGHT"
    np.testing.assert_array_equal(images.image_pixels(original), before)
    assert not color.get(images.COLOR_NORMALIZED_PROPERTY)
    np.testing.assert_allclose(images.image_pixels(color), before, atol=1 / 255)
    if sharing == "material":
        existing = bpy.data.materials["Existing"]
        assert next(n.image for n in existing.node_tree.nodes if n.type == "TEX_IMAGE") == original


def test_depth_plane_uses_submitted_color_and_aspect_after_resize(source, monkeypatch):
    expected = images.image_pixels(source.data)
    check_binding = conversion.conversion_source

    def resize_then_check(operator, scene):
        source.data.scale(1, 4)
        source.data.pixels.foreach_set(np.zeros(16, dtype=np.float32))
        return check_binding(operator, scene)

    monkeypatch.setattr(conversion, "conversion_source", resize_then_check)
    obj = run_conversion(source, "DEPTH", monkeypatch)
    color = next(node.image for node in obj.active_material.node_tree.nodes if node.type == "TEX_IMAGE")
    assert tuple(color.size) == (2, 1)
    np.testing.assert_allclose(images.image_pixels(color), expected, atol=1 / 255)
    vertices = np.array([vertex.co for vertex in obj.data.vertices])
    assert np.ptp(vertices[:, 0]) == pytest.approx(2 * np.ptp(vertices[:, 2]))


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
    if failure == "material":
        monkeypatch.setattr(material, "load_node_group", fail)
    elif failure == "finalize":
        monkeypatch.setattr(operators, "finalize_object_result", fail)
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
    if kind == "file":
        path = tmp_path / "source.png"
        Image.fromarray(np.array([[[51, 102, 204, 64], [153, 76, 25, 0]]], np.uint8)).save(path)
        source.data = bpy.data.images.load(str(path))
    if shared:
        share_image(source, "visible")
    obj = run_conversion(source, "PLANE", monkeypatch)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    expected = images.image_pixels(color)
    library = tmp_path / "converted.blend"
    bpy.data.libraries.write(str(library), {color})
    with bpy.data.libraries.load(str(library)) as (saved, loaded):
        loaded.images = saved.images
    restored = loaded.images[0]
    assert (restored.colorspace_settings.name, restored.alpha_mode) == (color.colorspace_settings.name, color.alpha_mode)
    np.testing.assert_allclose(images.image_pixels(restored), expected, atol=1 / 255)


@pytest.mark.parametrize("entry", ["DEPTH", "RELIEF"])
def test_depth_result_rejects_replaced_source_image(source, entry):
    operator = SimpleNamespace(_scene=bpy.context.scene, _source_object=source,
                               _source_image=source.data, plane_type=entry)
    source.data = source.data.copy()
    with pytest.raises(RuntimeError, match="source image has changed"):
        conversion.DepthPlaneJob.response(operator, bpy.context, None)


@pytest.mark.parametrize("shared", [False, True])
def test_plane_undo_redo_restores_image_configuration(source, monkeypatch, shared):
    if shared:
        share_image(source, "visible")
    original_name = source.data.name
    expected = images.image_pixels(source.data)
    bpy.context.preferences.edit.use_global_undo = True
    bpy.utils.register_class(operators.ConvertToPlane)
    try:
        bpy.ops.ed.undo_push(message="Before Plane")
        assert bpy.ops.anyimage.convert_to_plane("EXEC_DEFAULT", True) == {"FINISHED"}
        color_name = "Source_color.png"
        assert bpy.data.images[color_name].alpha_mode == "STRAIGHT"
        assert bpy.data.images[color_name].colorspace_settings.name == "AgX Base sRGB"
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert bpy.data.objects["Source"].type == "EMPTY"
        assert bpy.data.images[original_name].alpha_mode == "STRAIGHT"
        np.testing.assert_allclose(images.image_pixels(bpy.data.images[original_name]), expected, atol=1 / 255)
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert bpy.data.objects["Source"].type == "MESH"
        assert bpy.data.images[color_name].alpha_mode == "STRAIGHT"
        assert bpy.data.images[color_name].colorspace_settings.name == "AgX Base sRGB"
    finally:
        bpy.utils.unregister_class(operators.ConvertToPlane)


def test_conversion_source_survives_object_and_image_renaming(source):
    from anyimage.common.object import conversion_source

    operator = SimpleNamespace(_scene=bpy.context.scene, _source_object=source, _source_image=source.data)
    source.name = "Renamed source"
    source.data.name = "Renamed image"
    assert conversion_source(operator) == source


@pytest.mark.parametrize("change", ["pixels", "size", "color_space"])
def test_conversion_accepts_in_place_source_edits(source, change):
    from anyimage.common.object import conversion_source

    operator = SimpleNamespace(
        _source_object=source, _source_image=source.data,
    )
    if change == "pixels":
        source.data.pixels[0] = 0.8
    elif change == "size":
        source.data.scale(4, 2)
    else:
        source.data.colorspace_settings.name = "Non-Color"
    assert conversion_source(operator) == source
