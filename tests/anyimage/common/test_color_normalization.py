"""Verify inverse evaluation, fixed color mapping, and in-place image ownership."""

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import color_image, image as images, material
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


@pytest.mark.parametrize("space", [value for _, value in material.VIEW_TRANSFORM_COLOR_SPACES])
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


def test_normalization_clamps_channels_independently_before_gamma_and_encoding():
    rgba = np.array([[6, 2, 1, .5], [4, 4, 4, 1], [-1, 0, 100, 0]], dtype=np.float32)
    result = normalize_color_rgba(rgba)
    expected = [[1, .5 ** .75, .25 ** .75], [1, 1, 1], [0, 0, 1]]
    np.testing.assert_allclose(srgb_to_linear_rgb(result[:, :3]), expected, atol=2e-7)
    np.testing.assert_array_equal(result[:, 3], rgba[:, 3])
    np.testing.assert_array_equal(rgba[0], [6, 2, 1, .5])


def test_normalization_is_independent_of_surrounding_pixels_and_crop():
    pixel = np.array([[.5, 2, 8, .7]], dtype=np.float32)
    surrounding = np.tile([[10000, 0, 0, 1]], (100, 1))
    mixed = np.concatenate([pixel, surrounding])
    np.testing.assert_array_equal(normalize_color_rgba(mixed)[:1], normalize_color_rgba(pixel))


@pytest.mark.parametrize("rgba,expected", [
    ([[0, 0, 0, 1]], [[0, 0, 0]]),
    ([[-2, -1, 0, 1]], [[0, 0, 0]]),
    ([[.2, .1, .05, .5]], [[.05 ** .75, .025 ** .75, .0125 ** .75]]),
    ([[2, .5, -1, 0]], [[.5 ** .75, .125 ** .75, 0]]),
])
def test_normalization_handles_degenerate_ranges(rgba, expected):
    result = normalize_color_rgba(rgba)
    np.testing.assert_allclose(srgb_to_linear_rgb(result[:, :3]), expected, atol=2e-7)
    np.testing.assert_array_equal(result[:, 3], np.asarray(rgba)[:, 3])


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_pixels_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        normalize_color_rgba([[value, 0, 0, 1]])


@pytest.mark.parametrize("kind", ["generated", "file", "packed", "dirty"])
def test_normalization_is_in_place_and_survives_reload(source, kind, tmp_path, monkeypatch):
    if kind == "file":
        path = tmp_path / "source.png"
        Image.fromarray(np.uint8(np.rint(images.image_rgba(source) * 255))).save(path)
        source = bpy.data.images.load(str(path), check_existing=False)
    elif kind in {"packed", "dirty"}:
        source.pack()
        source.reload()
        if kind == "dirty":
            source.pixels[0] = .7
    before = images.image_rgba(source)
    expected = normalize_color_rgba(color_image.decode_color_image(source, "AgX Base sRGB"))
    identity = (source.as_pointer(), source.name, tuple(source.size), source.filepath_raw)
    resources = (set(bpy.data.images), set(bpy.data.scenes))
    scene = bpy.context.scene
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 2
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: False)
    assert material.configure_material_color_image(source, scene) == source
    assert (source.as_pointer(), source.name, tuple(source.size), source.filepath_raw) == identity
    assert (set(bpy.data.images), set(bpy.data.scenes)) == resources
    assert scene.view_settings.exposure == 2
    result = images.image_rgba(source)
    np.testing.assert_array_equal(result[..., 3], before[..., 3])
    np.testing.assert_allclose(result, expected, atol=1 / 255)
    assert source.colorspace_settings.name == "sRGB"
    assert source.alpha_mode == "PREMUL"
    assert source[images.COLOR_NORMALIZED_PROPERTY]
    assert not np.allclose(result[..., :3], before[..., :3])
    # A second call and a changed preference both preserve the normalized domain.
    for enabled in (False, True):
        monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: enabled)
        material.configure_material_color_image(source, scene)
        np.testing.assert_array_equal(images.image_rgba(source), result)
    library = tmp_path / "normalized.blend"
    bpy.data.libraries.write(str(library), {source})
    with bpy.data.libraries.load(str(library)) as (_, loaded):
        loaded.images = [source.name]
    restored = loaded.images[0]
    np.testing.assert_array_equal(images.image_rgba(restored), result)
    assert restored[images.COLOR_NORMALIZED_PROPERTY]
    with color_image.material_color_image(restored) as copied:
        assert copied[images.COLOR_NORMALIZED_PROPERTY]
        material.configure_material_color_image(copied, scene)
        np.testing.assert_array_equal(images.image_rgba(copied), result)

    # Verify the stored sRGB interpretation through an independent texture sample.
    opaque = result.copy()
    opaque[..., 3] = 1
    restored.pixels.foreach_set(np.flipud(opaque).ravel())
    restored.update()
    np.testing.assert_allclose(
        bake_texture_colors(restored), srgb_to_linear_rgb(result[..., :3]),
        rtol=5e-3, atol=1e-4,
    )


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
    monkeypatch.setattr(material, "configured_material_view_adaptation", lambda: False)

    def fail(*args, **kwargs):
        raise RuntimeError("Decode failed")

    monkeypatch.setattr(color_image.tempfile, "TemporaryDirectory", fail)
    with pytest.raises(RuntimeError, match="Decode failed"):
        material.configure_material_color_image(source, bpy.context.scene)
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
