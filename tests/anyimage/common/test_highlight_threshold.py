"""Verify spatial emission defaults and preservation of the complete source context."""

import bpy
import numpy as np
import pytest

from anyimage.common.color_image import estimate_highlight_threshold, material_color_image
from anyimage.common.image import COLOR_NORMALIZED_PROPERTY, image_rgba
from anyimage.common.material import create_image_material


@pytest.fixture(autouse=True)
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    yield
    bpy.ops.wm.read_factory_settings(use_empty=True)


def color_image(rgb, alpha=1, *, floating=True):
    """Create a top-down test image with straight RGB and explicit alpha."""
    height, width = rgb.shape[:2]
    image = bpy.data.images.new("Emission source", width=width, height=height,
                                alpha=True, float_buffer=floating)
    image.colorspace_settings.name = "Linear Rec.709" if floating else "sRGB"
    image.alpha_mode = "PREMUL" if floating else "STRAIGHT"
    rgba = np.ones((height, width, 4), np.float32)
    rgba[..., :3] = rgb
    rgba[..., 3] = alpha
    if floating:
        rgba[..., :3] *= rgba[..., 3:4]
    else:
        image[COLOR_NORMALIZED_PROPERTY] = True
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    return image


def layer_threshold(material):
    """Read the actual material node input."""
    layer = next(node for node in material.node_tree.nodes if node.type == "GROUP")
    return layer.inputs["Highlight Threshold"].default_value


def test_object_uses_surroundings_even_when_they_are_transparent():
    rgb = np.full((40, 40, 3), .1)
    rgb[10:30, 10:30] = .6
    opaque = color_image(rgb, floating=False)
    alpha = np.zeros((40, 40))
    alpha[10:30, 10:30] = 1
    cutout = color_image(rgb, alpha, floating=False)
    dark_threshold = estimate_highlight_threshold(opaque)
    assert estimate_highlight_threshold(cutout) == pytest.approx(dark_threshold)
    assert dark_threshold < .02
    rgb[alpha == 0] = 1
    light_surroundings = color_image(rgb, alpha, floating=False)
    assert estimate_highlight_threshold(light_surroundings) == pytest.approx(1)


@pytest.mark.parametrize("panorama", [False, True])
def test_spatial_defaults_scale_with_exposure_and_ignore_horizontal_orientation(panorama):
    rgb = np.full((41, 63, 3), .02)
    if panorama:
        rgb[:19] = np.linspace(.3, .8, 63)[None, :, None]
    else:
        rgb[10:31, 15:48] = np.linspace(.3, .8, 33)[None, :, None]
    image = color_image(rgb)
    baseline = estimate_highlight_threshold(image, panorama=panorama)
    for exposure in (.25, 4):
        result = estimate_highlight_threshold(color_image(rgb * exposure), panorama=panorama)
        assert result == pytest.approx(baseline * exposure, rel=1e-5)
    flipped = estimate_highlight_threshold(color_image(rgb[:, ::-1]), panorama=panorama)
    assert flipped == pytest.approx(baseline, rel=1e-5)
    if panorama:
        shifted = estimate_highlight_threshold(color_image(np.roll(rgb, 21, axis=1)), panorama=True)
        assert shifted == pytest.approx(baseline, rel=1e-5)
    material = create_image_material(image, image, panorama=panorama)
    assert layer_threshold(material) == pytest.approx(baseline)


def test_panorama_distinguishes_broad_sky_from_small_interior_windows():
    sky = np.full((60, 120, 3), .05)
    sky[:30] = .7
    sky[8:12, 75:80] = 10
    threshold = estimate_highlight_threshold(color_image(sky), panorama=True)
    assert .05 < threshold < .7 / 2
    room = np.full((60, 120, 3), .2)
    room[40:] = .6
    room[25:35, 75:99] = 10
    threshold = estimate_highlight_threshold(color_image(room), panorama=True)
    assert .6 < threshold < 10 / 2


@pytest.mark.parametrize("value,alpha", [(0, 1), (.5, 1), (4, 1), (.5, .1)])
def test_empty_and_flat_images_keep_default(value, alpha):
    image = color_image(np.full((1, 4, 3), value), alpha)
    assert estimate_highlight_threshold(image) == 1
    assert estimate_highlight_threshold(image, panorama=True) == 1


def test_fully_transparent_nonuniform_image_keeps_default():
    rgb = np.linspace(0, 1, 48).reshape(4, 4, 3)
    assert estimate_highlight_threshold(color_image(rgb, .05)) == 1


@pytest.mark.parametrize("view,panorama,floating", [
    ("Standard", False, False), ("AgX", False, False),
    ("AgX", True, False), ("AgX", True, True),
])
def test_cropped_material_inherits_full_source_threshold(view, panorama, floating):
    bpy.context.scene.view_settings.view_transform = view
    rgb = np.full((40, 60, 3), .05)
    rgb[10:30, 15:45] = np.linspace(.4, .9, 30)[None, :, None]
    if panorama:
        rgb[:10] = .8
    source = color_image(rgb, floating=floating)
    if not floating:
        del source[COLOR_NORMALIZED_PROPERTY]
    before = image_rgba(source)
    state = (source.colorspace_settings.name, source.alpha_mode)
    with material_color_image(source) as full:
        full_material = create_image_material(source, full, panorama=panorama)
    with material_color_image(source, bounds=(15, 10, 45, 30)) as cropped:
        cropped_material = create_image_material(source, cropped, panorama=panorama)
        assert layer_threshold(cropped_material) == pytest.approx(layer_threshold(full_material))
        assert estimate_highlight_threshold(cropped, panorama=panorama) != pytest.approx(
            layer_threshold(full_material), rel=.05,
        )
        assert tuple(cropped.size) == (30, 20)
    assert len(bpy.data.images) == 3
    assert (source.colorspace_settings.name, source.alpha_mode) == state
    np.testing.assert_array_equal(image_rgba(source), before)
