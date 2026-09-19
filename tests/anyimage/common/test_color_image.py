"""Verify isolated static color artifacts and source fidelity."""

from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import color_image as colors, image as images, material


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.images.new("Source.png", width=4, height=2, alpha=True)
    values = np.arange(32, dtype=np.float32).reshape(2, 4, 4) / 32
    values[0, 0, 3] = 0
    source.pixels.foreach_set(values.ravel())
    yield source
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("floating,alpha", [(False, "STRAIGHT"), (True, "STRAIGHT")])
@pytest.mark.parametrize("bounds", [None, (1, 0, 3, 2)])
def test_color_artifact_preserves_bounds_and_library_reload(source, tmp_path, monkeypatch, floating, alpha, bounds):
    if floating:
        source = bpy.data.images.new("Source.exr", width=4, height=2, alpha=True, float_buffer=True)
        source.pixels.foreach_set(np.tile(np.array([4, 2, .5, .25, 8, 3, 1, 0], dtype=np.float32), 4))
    source.alpha_mode = alpha
    source["anyimage_clipboard_sha256"] = "original"
    before = images.image_rgba(source)
    state = (source.filepath_raw, source.colorspace_settings.name, source.alpha_mode)
    path = colors.prepare_material_color_input(source, bounds)
    color = colors.load_material_color_image(path)
    try:
        assert color != source and color.name.endswith("_color" + path.suffix)
        assert "anyimage_clipboard_sha256" not in color
        assert Path(color.filepath_raw) == path
        expected = before if bounds is None else before[bounds[1]:bounds[3], bounds[0]:bounds[2]]
        np.testing.assert_allclose(images.image_rgba(color), expected, atol=1e-6 if floating else 1/255)
        monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: True)
        result = material.create_image_material(source, color)
        assert next(n.image for n in result.node_tree.nodes if n.type == "TEX_IMAGE") == color
        colors.cleanup_material_color_input(path)
        assert not path.parent.exists()
        library = tmp_path / "colors.blend"
        bpy.data.libraries.write(str(library), {color})
        with bpy.data.libraries.load(str(library)) as (saved, loaded):
            loaded.images = saved.images
        np.testing.assert_allclose(images.image_rgba(loaded.images[0]), expected, atol=1e-6 if floating else 1/255)
        if floating:
            assert color.colorspace_settings.name == "Linear Rec.709"
            assert color.alpha_mode == ("PREMUL" if alpha == "STRAIGHT" else alpha)
            layer = next(n for n in result.node_tree.nodes if n.type == "GROUP")
            assert layer.inputs["Alpha Fix"].default_value == 0
        assert (source.filepath_raw, source.colorspace_settings.name, source.alpha_mode) == state
        np.testing.assert_array_equal(images.image_rgba(source), before)
    finally:
        colors.cleanup_material_color_input(path)


def test_original_path_never_matches_material_color(tmp_path, monkeypatch):
    path = tmp_path / "original.png"
    Image.new("RGBA", (2, 2), (100, 150, 200, 128)).save(path)
    source = bpy.data.images.load(str(path), check_existing=False)
    with colors.material_color_image(source) as color:
        result = material.create_image_material(source, color)
        color.pixels[0] = 1
        bpy.data.images.remove(source)
        imported = bpy.data.images.load(str(path), check_existing=True)
        assert imported != color
        assert imported.alpha_mode == "STRAIGHT"
        assert images.image_pixels(imported)[0] == pytest.approx(100/255, abs=1/255)
        bpy.data.materials.remove(result)
    bpy.data.images.remove(imported)


@pytest.mark.parametrize("kind", ["MOVIE", "SEQUENCE"])
def test_static_input_rejects_single_frame_animation(kind):
    with pytest.raises(ValueError, match="static images"):
        colors.require_static_color_image(SimpleNamespace(source=kind, frame_duration=1))


@pytest.mark.parametrize("stage", ["export", "load", "material", "object"])
def test_failed_color_preparation_releases_owned_resources(source, tmp_path, monkeypatch, stage):
    directory = tmp_path / "owned-color"
    directory.mkdir()
    monkeypatch.setattr(colors.tempfile, "mkdtemp", lambda **_: str(directory))
    before = set(bpy.data.images)
    original = images.image_pixels(source)
    def fail(*_, **__):
        raise RuntimeError("Color failure")
    if stage == "export":
        monkeypatch.setattr(colors, "_save_byte_color", fail)
    elif stage == "load":
        monkeypatch.setattr(colors, "load_material_color_image", fail)
    elif stage == "material":
        monkeypatch.setattr(material, "material_node_group", fail)
    result = None
    try:
        with pytest.raises(RuntimeError, match="Color failure"):
            with colors.material_color_image(source) as color:
                result = material.create_image_material(source, color)
                fail()
    finally:
        if result is not None:
            bpy.data.materials.remove(result)
    assert set(bpy.data.images) == before
    assert not directory.exists()
    np.testing.assert_array_equal(images.image_pixels(source), original)


def test_ai_color_uses_submitted_crop_after_source_changes(source):
    from anyimage.operators.cutout_tool.operators import _generated_color_result
    bounds = (1, 0, 3, 2)
    expected = images.image_rgba(source)[:, 1:3].copy()
    with colors.material_color_image(source, bounds=bounds) as direct:
        path = colors.prepare_material_color_input(source, bounds)
        try:
            assert colors.material_analysis_input(path) == path
            source.pixels.foreach_set(np.zeros(32, np.float32))
            result, alpha, result_bounds = _generated_color_result(path, bounds)
            try:
                assert result_bounds == bounds and tuple(result.size) == (2, 2)
                np.testing.assert_array_equal(images.image_rgba(result), images.image_rgba(direct))
                np.testing.assert_allclose(images.image_rgba(result), expected, atol=1/255)
                np.testing.assert_allclose(alpha, expected[..., 3], atol=1/255)
            finally:
                bpy.data.images.remove(result)
        finally:
            colors.cleanup_material_color_input(path)


@pytest.mark.parametrize("color_space", ["Linear Rec.709", "sRGB", "Non-Color"])
def test_float_straight_uses_exr_interpretation_without_rejecting_hidden_rgb(source, tmp_path, color_space):
    source = bpy.data.images.new("Straight HDR", width=2, height=1, alpha=True, float_buffer=True)
    source.colorspace_settings.name = color_space
    rgba = np.array([4, 2, .5, .25, 8, 3, 1, 0], np.float32)
    source.pixels.foreach_set(rgba)
    with colors.material_color_image(source) as color:
        assert color.alpha_mode == "PREMUL"
        assert color.colorspace_settings.name == "Linear Rec.709"
        library = tmp_path / "straight.blend"
        bpy.data.libraries.write(str(library), {color})
        with bpy.data.libraries.load(str(library)) as (saved, loaded):
            loaded.images = saved.images
        np.testing.assert_array_equal(loaded.images[0].pixels[:], rgba)
    assert (source.colorspace_settings.name, source.alpha_mode) == (color_space, "STRAIGHT")
    np.testing.assert_array_equal(source.pixels[:], rgba)


def test_hdr_analysis_preview_is_separate_from_full_precision_color(source):
    source = bpy.data.images.new("HDR", width=2, height=1, alpha=True, float_buffer=True)
    source.alpha_mode = "PREMUL"
    source.pixels.foreach_set(np.array([4, 2, .5, .25, 8, 3, 1, 0], np.float32))
    path = colors.prepare_material_color_input(source)
    try:
        preview = colors.material_analysis_input(path)
        assert preview != path and preview.suffix == ".png" and path.suffix == ".exr"
        with Image.open(preview) as image:
            assert image.size == tuple(source.size)
        color = colors.load_material_color_image(path)
        try:
            np.testing.assert_array_equal(images.image_rgba(color), images.image_rgba(source))
        finally:
            bpy.data.images.remove(color)
    finally:
        colors.cleanup_material_color_input(path)
    assert not preview.exists()

