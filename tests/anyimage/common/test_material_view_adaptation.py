from types import SimpleNamespace
from unittest.mock import patch
import bpy
import numpy as np
import pytest
from PIL import Image


from anyimage import preferences
from anyimage.common import image as images
from anyimage.common import material
from anyimage.operators.clipboard_image import actions as clipboard
from tests.support.color_image import color_image


@pytest.fixture
def color_data():
    original_images = set(bpy.data.images)
    original_materials = set(bpy.data.materials)
    original_objects = set(bpy.data.objects)
    yield
    for obj in set(bpy.data.objects) - original_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for item in set(bpy.data.materials) - original_materials:
        bpy.data.materials.remove(item, do_unlink=True)
    for item in set(bpy.data.images) - original_images:
        bpy.data.images.remove(item, do_unlink=True)


def view_scene(view):
    return SimpleNamespace(view_settings=SimpleNamespace(view_transform=view))


def color_texture(result):
    return next(node.image for node in result.node_tree.nodes if node.type == "TEX_IMAGE")


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("view,space", [*material.VIEW_TRANSFORM_COLOR_SPACES, ("Standard", "sRGB"), ("Unknown", "sRGB")])
def test_color_space_and_alpha_follow_preference(color_data, enabled, view, space):
    image = bpy.data.images.new("Material policy", width=2, height=1, alpha=True)
    expected = np.array([0.2, 0.4, 0.8, 0.25, 0.6, 0.3, 0.1, 0], dtype=np.float32)
    image.pixels.foreach_set(expected)
    settings = SimpleNamespace(adapt_material_to_view_transform=enabled)
    # The installed bpy may not include newer view transforms such as ACES 2.0.
    try:
        image.colorspace_settings.name = space
    except TypeError:
        space = "sRGB"
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(expected)
    with patch.object(preferences, "addon_preferences", return_value=settings):
        result = material.configure_material_color_image(image, view_scene(view))
    selected = space if enabled else "sRGB"
    assert result.colorspace_settings.name == selected
    assert result.alpha_mode == ("PREMUL" if selected == "sRGB" else "STRAIGHT")
    assert settings.adapt_material_to_view_transform == enabled
    np.testing.assert_allclose(images.image_pixels(result), expected, atol=1 / 255)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("kind", [
    "byte", "packed", "file", "dirty",
    "float",
])
def test_material_pixels_survive_pack_and_library_reload(color_data, tmp_path, enabled, kind):
    expected = np.array([[[51, 102, 204, 64], [153, 76, 25, 0]]], dtype=np.uint8)
    if kind in {"file", "dirty"}:
        path = tmp_path / "source.png"
        Image.fromarray(expected).save(path)
        source = bpy.data.images.load(str(path), check_existing=False)
        if kind == "dirty":
            source.pixels.foreach_set((expected.astype(np.float32) / 255).ravel())
    else:
        source = bpy.data.images.new("Material pixels", width=2, height=1, alpha=True, float_buffer=kind == "float")
        source.alpha_mode = "PREMUL"
        source.pixels.foreach_set((expected.astype(np.float32) / 255).ravel())
        if kind == "packed":
            source.pack()
            source.reload()
    before = images.image_pixels(source)
    owner = bpy.data.objects.new("Color source owner", None)
    owner.empty_display_type = "IMAGE"
    owner.data = source
    with patch.object(material, "configured_material_view_adaptation", return_value=enabled):
        result = material.configure_material_color_image(source, view_scene("AgX"))
    assert result == source
    np.testing.assert_allclose(images.image_pixels(source), before, atol=1 / 255)
    np.testing.assert_allclose(images.image_pixels(result), before, atol=1 / 255)
    if result.packed_file is None or result.is_dirty:
        result.pack()
    selected = (result.colorspace_settings.name, result.alpha_mode)
    path = tmp_path / "material.blend"
    bpy.data.libraries.write(str(path), {result})
    with bpy.data.libraries.load(str(path)) as (available, loaded):
        loaded.images = available.images
    restored = loaded.images[0]
    assert (restored.colorspace_settings.name, restored.alpha_mode) == selected
    np.testing.assert_allclose(images.image_pixels(restored), before, atol=1 / 255)
    edited = images.create_image_edit_result(restored, images.image_pixels(restored), (2, 1))
    assert edited.alpha_mode == selected[1]
    np.testing.assert_allclose(images.image_pixels(edited), before, atol=1 / 255)


@pytest.mark.parametrize("shadeless", [False, True])
@pytest.mark.parametrize("entry", ["plane", "cutout", "depth", "clipboard"])
def test_material_configures_the_image_selected_by_its_caller(color_data, entry, shadeless):
    source = bpy.data.images.new("Shared source", width=2, height=2, alpha=True)
    source.pixels.foreach_set(np.tile(np.array([0.2, 0.4, 0.8, 0.25], dtype=np.float32), 4))
    owner = bpy.data.objects.new("Shared Empty", None)
    owner.empty_display_type = "IMAGE"
    owner.data = source
    before = images.image_pixels(source)
    scene = view_scene("AgX")
    settings = SimpleNamespace(adapt_material_to_view_transform=True)
    data_textures = {}
    if entry == "depth":
        for key in ("displacement_image", "normal_image"):
            image = bpy.data.images.new(key, width=2, height=2, float_buffer=True)
            image.colorspace_settings.name = "Non-Color"
            data_textures[key] = image
    data_states = {
        key: (image.colorspace_settings.name, image.alpha_mode, images.image_pixels(image))
        for key, image in data_textures.items()
    }
    with patch.object(preferences, "addon_preferences", return_value=settings):
        if entry == "clipboard":
            first = clipboard.create_image_material(source, source, shadeless=shadeless, scene=scene)
        else:
            if entry == "cutout":
                color = color_image(owner.data, (0, 0, 2, 2), images.image_rgba(source))
            else:
                color = source
            first = material.create_image_material(owner.data, color, 0, shadeless=shadeless, scene=scene, **data_textures)
        original_color = color_texture(first)
        assert original_color.colorspace_settings.name == "AgX Base sRGB"
        assert original_color.alpha_mode == "STRAIGHT"
        settings.adapt_material_to_view_transform = False
        assert original_color.alpha_mode == "STRAIGHT"
        if entry == "clipboard":
            second = clipboard.create_image_material(original_color, original_color, shadeless=shadeless, scene=scene)
        else:
            second = material.create_image_material(owner.data, original_color, 0, shadeless=shadeless, scene=scene)
        new_color = color_texture(second)
        assert new_color == original_color
        assert new_color.colorspace_settings.name == "sRGB"
        assert new_color.alpha_mode == "PREMUL"
        assert original_color.colorspace_settings.name == "sRGB"
        assert original_color.alpha_mode == "PREMUL"
        assert not settings.adapt_material_to_view_transform
    assert owner.data == source
    assert source.colorspace_settings.name == "sRGB"
    assert source.alpha_mode == ("STRAIGHT" if entry == "cutout" else "PREMUL")
    for image in (source, original_color, new_color):
        np.testing.assert_allclose(images.image_pixels(image), before, atol=1 / 255)
    for key, image in data_textures.items():
        space, alpha, pixels = data_states[key]
        assert image.colorspace_settings.name == space
        assert image.alpha_mode == alpha
        np.testing.assert_array_equal(images.image_pixels(image), pixels)


def test_edit_results_preserve_source_alpha_with_adaptation_enabled(color_data, tmp_path):
    source = bpy.data.images.new("Editing source", width=1, height=1, alpha=True)
    rgba = np.array([0.2, 0.4, 0.8, 0.25], dtype=np.float32)
    Image.fromarray(np.array([[[51, 102, 204, 64]]], dtype=np.uint8)).save(tmp_path / "foreground.png")
    with patch.object(preferences, "addon_preferences", return_value=SimpleNamespace(adapt_material_to_view_transform=True)):
        edited = images.create_image_edit_result(source, rgba, (1, 1))
        loaded = images.load_image_edit_result(source, tmp_path / "foreground.png")
    for result in (edited, loaded):
        assert result.colorspace_settings.name == "sRGB"
        assert result.alpha_mode == source.alpha_mode
        np.testing.assert_allclose(images.image_pixels(result), rgba, atol=1 / 255)
    assert source.colorspace_settings.name == "sRGB"
    assert source.alpha_mode == "STRAIGHT"
