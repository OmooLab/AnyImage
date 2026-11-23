"""Verify clipboard brush textures, previews and saved bindings."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import bpy
import numpy as np
import pytest

from anyimage.common import color_image, image as images
from anyimage.common.color_space import normalize_color_rgba
from anyimage.operators.clipboard_image import actions, cache
from anyimage.operators.clipboard_image import brush as brush_tools


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
        source = color_image.create_normalized_color_image(source)
    source.pixels.foreach_set(pixels)
    source.update()
    source.pack()
    expected = (
        normalize_color_rgba(color_image.decode_color_image(source, source.colorspace_settings.name))
        if kind == "inverse" else images.image_rgba(source)
    )
    source_settings = source.colorspace_settings.name, source.alpha_mode
    before = images.image_pixels(source)
    texture = brush_tools.set_tool_texture(context, source)
    bound = texture.image
    assert (bound == source) == (kind in {"hdr", "normalized"})
    assert (source.colorspace_settings.name, source.alpha_mode) == source_settings
    np.testing.assert_array_equal(images.image_pixels(source), before)
    assert bound.colorspace_settings.name == ("Linear Rec.709" if kind == "hdr" else "sRGB")
    if kind != "hdr":
        assert bound.alpha_mode == "PREMUL" and bound.file_format == "PNG"
        assert bound[images.COLOR_NORMALIZED_PROPERTY]
    np.testing.assert_allclose(images.image_rgba(bound), expected, atol=1 / 255)


@pytest.mark.parametrize("mode", ["SCULPT", "PAINT_TEXTURE", "PAINT_VERTEX"])
def test_brush_modes_bind_normalized_texture(source, context, mode):
    context.mode = mode
    texture = brush_tools.set_tool_texture(context, source)
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
    source[cache.CLIPBOARD_CONTENT_PROPERTY] = cache._clipboard_content_hash(source)
    texture = brush_tools.set_tool_texture(context, source)
    assert cache._find_packed_clipboard_image("original") == source
    before = images.image_pixels(texture.image)
    assert brush_tools.set_tool_texture(context, texture.image) == texture
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
    resources = set(bpy.data.images), set(bpy.data.textures)
    with pytest.raises(RuntimeError, match="Brush failed"):
        brush_tools.set_tool_texture(context, source)
    np.testing.assert_array_equal(images.image_pixels(source), before)
    assert bytes(source.packed_file.data) == packed
    assert source.is_float == is_float
    assert source.colorspace_settings.name == ("Linear Rec.709" if is_float else "AgX Base sRGB")
    assert not source.get(images.COLOR_NORMALIZED_PROPERTY)
    assert brush.texture is None and brush.texture_slot.texture is None
    assert brush.texture_slot.map_mode == "VIEW_PLANE"
    assert (set(bpy.data.images), set(bpy.data.textures)) == resources


def test_failed_preview_export_restores_format_and_removes_directory():
    image = SimpleNamespace(file_format="OPEN_EXR", save=Mock(side_effect=OSError("disk full")))
    with pytest.raises(RuntimeError, match="disk full"):
        brush_tools.set_brush_preview(bpy.context, None, image)
    assert image.file_format == "OPEN_EXR"
    assert not Path(image.save.call_args.kwargs["filepath"]).parent.exists()


def test_packed_brush_replacement_updates_preview_and_survives_reopen(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Preview Source", width=80, height=40, alpha=True)
    pixels = np.zeros((40, 80, 4), dtype=np.float32)
    pixels[:, :40] = (1.0, 0.0, 0.0, 1.0)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    image.file_format = "JPEG"
    original_pixels = tuple(image.pixels)
    original_format = image.file_format
    brush = bpy.data.brushes.new("Preview Brush", mode="TEXTURE_PAINT")
    brush.asset_mark()
    texture = bpy.data.textures.new("Preview Texture", type="IMAGE")
    texture.image = image
    brush.texture = texture
    try:
        brush_tools.set_brush_preview(bpy.context, brush, image)
        assert tuple(brush.preview.image_size) == (80, 40)
        preview = np.array(brush.preview.image_pixels_float[:]).reshape(40, 80, 4)
        assert np.allclose(preview[:, :40, 0], 1.0, atol=1 / 255)
        assert np.all(preview[:, :40, 3] == 1.0)
        assert np.all(preview[:, 40:, 3] == 0.0)
        assert tuple(image.pixels) == original_pixels
        assert tuple(image.size) == (80, 40)
        assert image.packed_file is not None
        assert image.file_format == original_format
        replacement = bpy.data.images.new("Incoming", width=40, height=80, alpha=True)
        replacement.pixels[:] = [0, 1, 0, 1] * (40 * 80)
        replacement.pack()
        context = SimpleNamespace(
            mode="PAINT_TEXTURE", scene=bpy.context.scene,
            temp_override=bpy.context.temp_override,
        )
        pasted = actions.replace_pasted_image(actions.ClipboardImageTarget(image, texture, brush), replacement)
        brush_tools.set_brush_preview(context, brush, pasted)
        bpy.data.images.remove(replacement)
        assert brush.texture == texture and texture.image == image
        assert image.name == "Preview Source" and tuple(image.size) == (40, 80)
        assert tuple(brush.preview.image_size) == (40, 80)
        preview = np.array(brush.preview.image_pixels_float[:]).reshape(80, 40, 4)
        np.testing.assert_allclose(preview, np.tile([0, 1, 0, 1], (80, 40, 1)), atol=1 / 255)
        expected_preview = tuple(brush.preview.image_pixels)
        path = str(tmp_path / "brush-preview.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        restored = bpy.data.brushes["Preview Brush"]
        assert tuple(restored.preview.image_size) == (40, 80)
        assert tuple(restored.preview.image_pixels) == expected_preview
        assert restored.texture.name == "Preview Texture"
        assert restored.texture.image.name == "Preview Source"
        assert tuple(restored.texture.image.size) == (40, 80)
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)
