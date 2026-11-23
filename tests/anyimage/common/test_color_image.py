"""Verify isolated static color artifacts and source fidelity."""

from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import color_image as colors, image as images, material
from anyimage.common.image_input import cleanup_image_input, prepare_ai_input
from anyimage.server.media.input import load_ai_input


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.images.new("Source.png", width=4, height=2, alpha=True)
    values = np.arange(32, dtype=np.float32).reshape(2, 4, 4) / 32
    values[0, 0, 3] = 0
    source.pixels.foreach_set(values.ravel())
    yield source
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("floating,alpha,bounds", [(False, "STRAIGHT", (1, 0, 3, 2)), (True, "STRAIGHT", None)])
def test_color_artifact_preserves_bounds_and_library_reload(source, tmp_path, floating, alpha, bounds):
    if floating:
        source = bpy.data.images.new("Source.exr", width=4, height=2, alpha=True, float_buffer=True)
        source.pixels.foreach_set(np.tile(np.array([4, 2, .5, .25, 8, 3, 1, 0], dtype=np.float32), 4))
    source.alpha_mode = alpha
    source["anyimage_clipboard_sha256"] = "original"
    before = images.image_rgba(source)
    state = (source.filepath_raw, source.colorspace_settings.name, source.alpha_mode)
    color = colors.create_material_color_image(source, bounds)
    assert color != source and color.name.endswith("_color.exr" if floating else "_color.png")
    assert "anyimage_clipboard_sha256" not in color
    assert color.packed_file
    expected = before if bounds is None else before[bounds[1]:bounds[3], bounds[0]:bounds[2]]
    np.testing.assert_allclose(images.image_rgba(color), expected, atol=1e-6 if floating else 1/255)
    result = material.create_image_material(source, color, panorama=True)
    assert next(n.image for n in result.node_tree.nodes if n.type == "TEX_IMAGE") == color
    library = tmp_path / "colors.blend"
    bpy.data.libraries.write(str(library), {color})
    with bpy.data.libraries.load(str(library)) as (saved, loaded):
        loaded.images = saved.images
    np.testing.assert_allclose(images.image_rgba(loaded.images[0]), expected, atol=1e-6 if floating else 1/255)
    if floating:
        assert color.colorspace_settings.name == "Linear Rec.709"
        assert color.alpha_mode == ("PREMUL" if alpha == "STRAIGHT" else alpha)
        layer = next(n for n in result.node_tree.nodes if n.type == "GROUP")
        assert layer.inputs["Alpha Scale"].default_value == 1
    assert (source.filepath_raw, source.colorspace_settings.name, source.alpha_mode) == state
    np.testing.assert_array_equal(images.image_rgba(source), before)


def test_straight_exr_material_uses_visible_hdr_after_file_changes(tmp_path):
    from anyimage.common.hdr_image import save_hdr_image

    path = tmp_path / "lighting.exr"
    rgba = np.array([[[8, 4, 1, .5], [12, 3, 2, 1]]], np.float32)
    save_hdr_image(rgba, path)
    source = bpy.data.images.load(str(path), check_existing=False)
    try:
        source.alpha_mode = "STRAIGHT"
        visible = images.image_rgba(source)
        save_hdr_image(np.ones((2, 1, 4), np.float32), path)
        with colors.material_color_image(source) as color:
            assert color.is_float and color.file_format == "OPEN_EXR"
            np.testing.assert_array_equal(images.image_rgba(color), visible)
        assert source.alpha_mode == "STRAIGHT" and not source.is_dirty
    finally:
        bpy.data.images.remove(source)


def test_original_path_never_matches_material_color(tmp_path):
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


@pytest.mark.parametrize("stage", ["export", "material", "object"])
def test_failed_color_preparation_releases_owned_resources(source, tmp_path, monkeypatch, stage):
    monkeypatch.setattr(colors.tempfile, "tempdir", str(tmp_path))
    before = set(bpy.data.images)
    original = images.image_pixels(source)
    def fail(*_, **__):
        raise RuntimeError("Color failure")
    if stage == "export":
        monkeypatch.setattr(colors, "save_color_png", fail)
    elif stage == "material":
        monkeypatch.setattr(material, "load_node_group", fail)
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
    assert not list(tmp_path.iterdir())
    np.testing.assert_array_equal(images.image_pixels(source), original)


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


@pytest.mark.parametrize("floating,space,gray,expected", [
    (False, "sRGB", .5, 128),
    (False, "Non-Color", .5, 128),
    (False, "Linear Rec.709", .5, 188),
    (True, "Linear Rec.709", 2.0, 231),
])
def test_recognition_crop_is_srgb_with_source_opacity(source, floating, space, gray, expected):
    image = bpy.data.images.new("Cutout", width=3, height=1, alpha=True, float_buffer=floating)
    image.colorspace_settings.name = space
    image.alpha_mode = "PREMUL" if floating else "STRAIGHT"
    image.pixels.foreach_set(np.array([1, 0, 0, 1, gray, gray, gray, .5, 0, 0, 0, 0], np.float32))
    crop = images.image_rgba(image)[:, 1:]
    before = crop.copy()
    path = prepare_ai_input(image, crop)
    try:
        assert list(path.parent.iterdir()) == [path]
        pixels = np.load(path)
        assert pixels.shape == crop.shape
        assert pixels.dtype == (np.float32 if floating or space == "Linear Rec.709" else np.uint8)
        model_rgba = load_ai_input(path)
        np.testing.assert_allclose(model_rgba[0, 0, :3], expected / 255, atol=.5 / 255)
        np.testing.assert_allclose(model_rgba[..., 3], crop[..., 3], atol=1e-7)
        np.testing.assert_array_equal(crop, before)
    finally:
        cleanup_image_input(path)


@pytest.mark.parametrize("dtype,white", [(np.uint8, 255), (np.uint16, 65535)])
def test_srgb_png_bit_depth_preserves_ai_brightness(tmp_path, dtype, white):
    path = tmp_path / "gray.png"
    levels = np.array([[0, 128, 255]], dtype=dtype) * (white // 255)
    Image.fromarray(levels).save(path)
    image = bpy.data.images.load(str(path))
    try:
        assert image.colorspace_settings.name == "sRGB"
        assert image.is_float == (dtype == np.uint16)
        snapshot = prepare_ai_input(image, images.image_rgba(image))
        try:
            np.testing.assert_allclose(load_ai_input(snapshot)[0, :, 0], [0, 128 / 255, 1], atol=1e-4)
        finally:
            cleanup_image_input(snapshot)
    finally:
        bpy.data.images.remove(image)


def test_resized_byte_image_keeps_interpolated_rgba(source):
    rgba = images.image_rgba(source)
    path = prepare_ai_input(source, rgba, max_input_size=2, panorama=True)
    try:
        pixels = np.load(path)
        assert pixels.dtype == np.float32 and pixels.shape == (1, 2, 4)
        expected_alpha = Image.fromarray(rgba[..., 3]).resize((2, 1), Image.Resampling.BOX)
        np.testing.assert_array_equal(pixels[..., 3], np.asarray(expected_alpha))
    finally:
        cleanup_image_input(path)


def test_hdr_crop_uses_the_same_mapping_as_the_full_image(tmp_path):
    path = tmp_path / "edited.png"
    Image.fromarray(np.full((1, 3), 32768, np.uint16)).save(path)
    image = bpy.data.images.load(str(path))
    paths = []
    try:
        image.pixels[0:4] = (2, 2, 2, 1)
        image.update()
        rgba = images.image_rgba(image)
        paths.append(prepare_ai_input(image, rgba))
        paths.append(prepare_ai_input(image, rgba, bounds=(1, 0, 3, 1)))
        full, crop = (np.load(p) for p in paths)
        np.testing.assert_array_equal(crop, full[:, 1:])
        assert 0.45 < crop[0, 0, 0] < 0.47
        assert rgba[0, 0, 0] == 2
    finally:
        for snapshot in paths:
            cleanup_image_input(snapshot)
        bpy.data.images.remove(image)


def test_wide_gamut_16bit_tiff_keeps_sdr_midtone_brightness(tmp_path):
    from anyimage.common.hdr_image import is_hdr_source

    path = tmp_path / "p3.tiff"
    source = bpy.data.images.new("P3 swatches", 2, 1, alpha=True, float_buffer=True)
    scene = bpy.data.scenes.new("SDR export")
    try:
        source.pixels[:] = (1, 0, 0, 1, .21586, .21586, .21586, 1)
        scene.view_settings.view_transform = "Standard"
        settings = scene.render.image_settings
        settings.file_format = "TIFF"
        settings.color_depth = "16"
        source.save_render(str(path), scene=scene)
    finally:
        bpy.data.images.remove(source)
        bpy.data.scenes.remove(scene)
    image = bpy.data.images.load(str(path))
    snapshot = None
    try:
        image.colorspace_settings.name = "Display P3"
        rgba = images.image_rgba(image)
        assert rgba[0, 0, 0] > 1 and not is_hdr_source(image, rgba)
        snapshot = prepare_ai_input(image, rgba)
        np.testing.assert_array_equal(load_ai_input(snapshot, as_bytes=True)[0, 1], (128, 128, 128, 255))
    finally:
        cleanup_image_input(snapshot)
        bpy.data.images.remove(image)


def test_byte_snapshot_matches_blender_for_a_transparent_crop(source, tmp_path):
    rgba = images.image_rgba(source)[:, :3]
    rgba[0, 1] = (1, .5, .25, 0)
    rgba[1, 2] = (.5 / 255, .5, 1.5, .5)
    expected = tmp_path / "blender.png"
    colors.save_color_png(rgba, expected, "sRGB")
    path = prepare_ai_input(source, rgba)
    try:
        with Image.open(expected) as reference:
            np.testing.assert_array_equal(np.load(path), np.asarray(reference))
    finally:
        cleanup_image_input(path)
