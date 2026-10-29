"""Verify normalized brush textures, cache ownership and failed bindings."""

from types import SimpleNamespace

import bpy
import numpy as np
import pytest

from anyimage.common import color_image, image as images
from anyimage.common.color_space import normalize_color_rgba
from anyimage.operators.clipboard_image import actions


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Brush.png", width=4, height=1, alpha=True)
    image.pixels.foreach_set([.2, .4, .8, .25, .9, .7, .3, 1, .5, .5, .5, 0, .1, .05, .2, .7])
    yield image
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.fixture
def context(monkeypatch):
    brush = SimpleNamespace(
        texture=None, texture_slot=SimpleNamespace(texture=None, map_mode="VIEW_PLANE"),
        stencil_dimension=(256, 256), update_tag=lambda: None,
    )
    monkeypatch.setattr(actions, "_set_brush_preview", lambda *args: None)
    return SimpleNamespace(mode="PAINT_TEXTURE", brush=brush, scene=bpy.context.scene)


@pytest.mark.parametrize("kind", ["srgb", "inverse", "hdr", "normalized"])
def test_brush_color_preserves_hdr_and_normalizes_byte_images(source, context, kind):
    pixels = images.image_pixels(source)
    if kind == "hdr":
        source.use_generated_float = True
        source.colorspace_settings.name = "Linear Rec.709"
        pixels.reshape(-1, 4)[:, :3] *= 8
    elif kind == "inverse":
        source.colorspace_settings.name = "AgX Base sRGB"
    elif kind == "normalized":
        source[images.COLOR_NORMALIZED_PROPERTY] = True
    source.pixels.foreach_set(pixels)
    source.update()
    source.pack()
    expected = (
        normalize_color_rgba(color_image.decode_color_image(source, source.colorspace_settings.name))
        if kind == "inverse" else images.image_rgba(source)
    )
    identity = (source.as_pointer(), source.name, source.filepath_raw)
    resources = (set(bpy.data.images), set(bpy.data.scenes))
    texture = actions.set_tool_texture(context, source)
    assert texture.image == source
    assert source.is_float == (kind == "hdr")
    assert source.colorspace_settings.name == ("Linear Rec.709" if kind == "hdr" else "sRGB")
    if kind != "hdr":
        assert source.alpha_mode == "PREMUL" and source.file_format == "PNG"
        assert source[images.COLOR_NORMALIZED_PROPERTY]
    assert (source.as_pointer(), source.name, source.filepath_raw) == identity
    assert (set(bpy.data.images), set(bpy.data.scenes)) == resources
    np.testing.assert_allclose(images.image_rgba(source), expected, atol=1 / 255)


@pytest.mark.parametrize("mode", ["SCULPT", "PAINT_TEXTURE", "PAINT_VERTEX"])
def test_brush_modes_bind_normalized_texture(source, context, mode):
    context.mode = mode
    texture = actions.set_tool_texture(context, source)
    assert context.brush.texture == context.brush.texture_slot.texture == texture
    assert context.brush.texture_slot.map_mode == "STENCIL"
    assert texture.image[images.COLOR_NORMALIZED_PROPERTY]


def test_brush_cache_and_saved_texture_preserve_normalized_content(source, context, tmp_path):
    pixels = images.image_pixels(source)
    source.colorspace_settings.name = "AgX Base sRGB"
    source.pixels.foreach_set(pixels)
    source.update()
    source.pack()
    source[actions.CLIPBOARD_HASH_PROPERTY] = "original"
    source[actions.CLIPBOARD_CONTENT_PROPERTY] = actions._clipboard_content_hash(source)
    texture = actions.set_tool_texture(context, source)
    assert actions._find_packed_clipboard_image("original") is None
    before = images.image_pixels(source)
    assert actions.set_tool_texture(context, source) == texture
    np.testing.assert_array_equal(images.image_pixels(source), before)
    library = tmp_path / "brush-color.blend"
    bpy.data.libraries.write(str(library), {texture})
    with bpy.data.libraries.load(str(library)) as (_, loaded):
        loaded.textures = [texture.name]
    restored = loaded.textures[0].image
    assert restored.colorspace_settings.name == "sRGB" and not restored.is_float
    assert restored[images.COLOR_NORMALIZED_PROPERTY]
    np.testing.assert_array_equal(images.image_pixels(restored), before)

@pytest.mark.parametrize("is_float", [False, True])
def test_brush_failure_rolls_back_normalized_image_and_binding(source, context, is_float):
    pixels = images.image_pixels(source)
    source.use_generated_float = is_float
    source.colorspace_settings.name = "Linear Rec.709" if is_float else "AgX Base sRGB"
    if is_float:
        pixels.reshape(-1, 4)[:, :3] *= 2
    source.pixels.foreach_set(pixels)
    source.update()
    source.pack()
    before = images.image_pixels(source)
    packed = bytes(source.packed_file.data)

    def fail():
        raise RuntimeError("Brush failed")

    brush = context.brush
    brush.update_tag = fail
    textures = set(bpy.data.textures)
    with pytest.raises(actions.PasteTargetError, match="Brush failed"):
        actions.set_tool_texture(context, source)
    np.testing.assert_array_equal(images.image_pixels(source), before)
    assert bytes(source.packed_file.data) == packed
    assert source.is_float == is_float
    assert source.colorspace_settings.name == ("Linear Rec.709" if is_float else "AgX Base sRGB")
    assert not source.get(images.COLOR_NORMALIZED_PROPERTY)
    assert brush.texture is None and brush.texture_slot.texture is None
    assert brush.texture_slot.map_mode == "VIEW_PLANE"
    assert set(bpy.data.textures) == textures
