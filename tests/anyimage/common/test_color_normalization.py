"""Verify inverse evaluation, fixed color mapping, and in-place image ownership."""

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import color_image, image as images
from anyimage.common.color_space import normalize_color_rgba, srgb_to_linear_rgb
from anyimage.common.job_image import load_image_edit_result


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Source_color.png", width=4, height=1, alpha=True)
    image.pixels.foreach_set([
        .2, .4, .8, .25, .9, .7, .3, 1, .5, .5, .5, 0, .1, .05, .2, .7,
    ])
    yield image
    bpy.ops.wm.read_factory_settings(use_empty=True)


def bake_texture_colors(image):
    """Sample the source through Cycles, independently of the image export path."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.render.bake.margin = 0
    mesh = bpy.data.meshes.new("Color card")
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new()
    for loop, value in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = value
    obj = bpy.data.objects.new("Color card", mesh)
    scene.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mat = bpy.data.materials.new("Color card")
    mat.use_nodes = True
    mesh.materials.append(mat)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Closest"
    emission = nodes.new("ShaderNodeEmission")
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs[0], nodes.get("Material Output").inputs["Surface"])
    target = nodes.new("ShaderNodeTexImage")
    target.image = bpy.data.images.new("Float samples", width=4, height=1, float_buffer=True)
    nodes.active = target
    bpy.ops.object.bake(type="EMIT")
    return images.image_rgba(target.image)[..., :3]


@pytest.mark.parametrize("space", [value for _, value in color_image.VIEW_TRANSFORM_COLOR_SPACES])
def test_inverse_decode_matches_cycles_with_hidden_colors(source, space):
    source.pack()
    try:
        source.colorspace_settings.name = space
    except TypeError:
        pytest.skip(f"Blender {bpy.app.version_string} does not provide {space}")
    rgba = images.image_rgba(source)
    baseline = (set(bpy.data.images), set(bpy.data.scenes))
    decoded = color_image.decode_color_image(source, space)
    assert (set(bpy.data.images), set(bpy.data.scenes)) == baseline
    np.testing.assert_array_equal(decoded[..., 3], rgba[..., 3])
    # Sample opaque colors so Cycles' alpha premultiplication cannot hide RGB.
    opaque = rgba.copy()
    opaque[..., 3] = 1
    source.pixels.foreach_set(np.flipud(opaque).ravel())
    source.update()
    np.testing.assert_allclose(
        decoded[..., :3], bake_texture_colors(source), rtol=5e-3, atol=1e-4,
    )


def test_normalization_preserves_alpha_and_input_with_bounded_rgb():
    rgba = np.array([[6, 2, 1, .5], [4, 4, 4, 1], [-1, 0, 100, 0]], dtype=np.float32)
    original = rgba.copy()
    result = normalize_color_rgba(rgba)
    assert np.min(result[..., :3]) >= 0 and np.max(result[..., :3]) <= 1
    np.testing.assert_array_equal(result[:, 3], rgba[:, 3])
    np.testing.assert_array_equal(rgba, original)


def test_normalization_is_independent_of_surrounding_pixels_and_crop():
    pixel = np.array([[.5, 2, 8, .7]], dtype=np.float32)
    surrounding = np.tile([[10000, 0, 0, 1]], (100, 1))
    mixed = np.concatenate([pixel, surrounding])
    np.testing.assert_array_equal(normalize_color_rgba(mixed)[:1], normalize_color_rgba(pixel))


@pytest.mark.parametrize("rgba,expected", [
    ([[0, 0, 0, 1]], [[0, 0, 0]]),
    ([[-2, -1, 0, 1]], [[0, 0, 0]]),
    ([[.25, .25, .25, .5]], [[0.205615783986] * 3]),
    ([[4, 8, 16, 0]], [[1, 1, 1]]),
])
def test_normalization_maps_neutral_brightness_and_handles_black(rgba, expected):
    result = normalize_color_rgba(rgba)
    np.testing.assert_allclose(srgb_to_linear_rgb(result[:, :3]), expected, atol=2e-7)
    np.testing.assert_array_equal(result[:, 3], np.asarray(rgba)[:, 3])


def test_normalization_lifts_highlights_with_a_bounded_monotonic_curve():
    values = np.array([0, .01, .1, .5, .839, 1], np.float32)
    # Supply scene-linear values whose gamma result equals the curve input.
    levels = 4 * values ** (1 / .65)
    rgba = np.column_stack((levels, levels, levels, np.ones_like(levels)))
    linear = srgb_to_linear_rgb(normalize_color_rgba(rgba)[:, :3])[:, 0]
    assert np.all(np.diff(linear) > 0)
    assert np.min(linear) >= 0 and np.max(linear) <= 1
    assert linear[1] == pytest.approx(.01, abs=.0003)
    assert linear[3] == pytest.approx(.738796125, abs=2e-7)
    assert linear[4] == pytest.approx(.98776, abs=.0001)
    assert np.all(linear[1:-1] > values[1:-1])


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_pixels_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        normalize_color_rgba([[value, 0, 0, 1]])


def test_edits_preserve_state_and_fresh_replacement_clears_it(source, tmp_path):
    source[images.COLOR_NORMALIZED_PROPERTY] = True
    edited = images.create_image_edit_result(source, images.image_pixels(source), (4, 1))
    assert edited[images.COLOR_NORMALIZED_PROPERTY]
    path = tmp_path / "edit.png"
    Image.new("RGBA", (4, 1), (10, 20, 30, 255)).save(path)
    result = load_image_edit_result(source, path)
    images.restore_image_content(source, images.image_content_state(result))
    assert source[images.COLOR_NORMALIZED_PROPERTY]
    fresh = bpy.data.images.load(str(path), check_existing=False)
    images.restore_image_content(source, images.image_content_state(fresh))
    assert not source.get(images.COLOR_NORMALIZED_PROPERTY)


def test_failed_decode_restores_content_and_releases_resources(source, monkeypatch):
    source.pack()
    source.pixels[0] = .7
    before = images.image_pixels(source)
    packed = bytes(source.packed_file.data)
    resources = (set(bpy.data.images), set(bpy.data.scenes))

    def fail(*args, **kwargs):
        raise RuntimeError("Decode failed")

    monkeypatch.setattr(color_image.tempfile, "TemporaryDirectory", fail)
    with pytest.raises(RuntimeError, match="Decode failed"):
        color_image.decode_color_image(source, "AgX Base sRGB")
    np.testing.assert_array_equal(images.image_pixels(source), before)
    assert source.colorspace_settings.name == "sRGB"
    assert bytes(source.packed_file.data) == packed
    assert not source.get(images.COLOR_NORMALIZED_PROPERTY)
    assert (set(bpy.data.images), set(bpy.data.scenes)) == resources


def test_float_decode_preserves_hdr_values_and_matches_cycles(source):
    image = bpy.data.images.new("HDR source", width=4, height=1, alpha=True, float_buffer=True)
    image.colorspace_settings.name = "Linear Rec.709"
    rgba = np.array([[[6, 2, 1, .5], [4, 4, 4, 1], [.2, .4, .8, 0], [1, 3, 5, .7]]], np.float32)
    image.pixels.foreach_set(rgba.ravel())
    decoded = color_image.decode_color_image(image, image.colorspace_settings.name)
    np.testing.assert_allclose(decoded, rgba, atol=1e-6)
    opaque = rgba.copy()
    opaque[..., 3] = 1
    image.pixels.foreach_set(opaque.ravel())
    np.testing.assert_allclose(decoded[..., :3], bake_texture_colors(image), atol=1e-5)


@pytest.mark.parametrize("space,is_float", [("sRGB", False), ("AgX Base sRGB", False), ("Non-Color", True), ("Linear Rec.709", True)])
def test_normalized_color_is_bounded_repeatable_and_preserves_source(space, is_float):
    from anyimage.common.color_image import decode_color_image
    from anyimage.common.color_space import normalize_color_rgba
    from anyimage.common.image import COLOR_NORMALIZED_PROPERTY, image_rgba
    from anyimage.common.color_image import create_normalized_color_image

    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.images.new("Color", width=4, height=1, alpha=True, float_buffer=is_float)
    source.colorspace_settings.name = space
    pixels = np.array([[.2, .4, .8, .25], [.9, .7, .3, 1], [.5, .5, .5, 0], [.1, .05, .2, .7]], np.float32)
    if is_float:
        pixels[:, :3] *= 10
        pixels[0, 0] = -1
    source.pixels.foreach_set(pixels.ravel())
    original = images.image_pixels(source).copy()
    expected = image_rgba(source) if space == "sRGB" else normalize_color_rgba(decode_color_image(source, space))
    result = create_normalized_color_image(source)
    try:
        assert not result.is_float and result.colorspace_settings.name == "sRGB"
        assert result[COLOR_NORMALIZED_PROPERTY]
        assert bytes(result.packed_file.data).startswith(b"\x89PNG\r\n\x1a\n")
        np.testing.assert_allclose(image_rgba(result), expected, atol=1 / 255)
        assert np.min(images.image_pixels(result)) >= 0 and np.max(images.image_pixels(result)) <= 1
        again = create_normalized_color_image(result)
        try:
            np.testing.assert_array_equal(images.image_pixels(again), images.image_pixels(result))
        finally:
            bpy.data.images.remove(again)
        np.testing.assert_array_equal(images.image_pixels(source), original)
        assert source.colorspace_settings.name == space and source.is_float == is_float
    finally:
        bpy.data.images.remove(result)
        bpy.data.images.remove(source)
