import bpy
import numpy as np
import pytest
from anyimage import properties
from anyimage.common import color_reference as reference_cache
from anyimage.common.image import image_rgba, is_color_reference_candidate
from anyimage.common.color_space import srgb_to_linear_rgb
from tests.support.color_reference import create_rgba_image, registered_color_reference, isolate_reference_cache


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Reference", True),
        ("Reference.PNG", True),
        ("Subject_normal", False),
        ("Subject_DEPTH", False),
        ("Subject_color", False),
        ("Subject_normal.001", False),
        ("Subject_depth.exr.002", False),
        ("Subject_color.png.003", False),
    ],
)
def test_color_reference_candidate_filters_generated_image_names(name, expected):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = create_rgba_image(name, np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    assert is_color_reference_candidate(image) is expected


def test_color_reference_candidate_rejects_animated_images():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = create_rgba_image("Sequence", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    image.source = "SEQUENCE"
    assert not is_color_reference_candidate(image)


def test_reference_cache_refreshes_consecutive_pixel_edits(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rgba = np.full((4, 4, 4), (0.7, 0.2, 0.1, 1.0), dtype=np.float32)
    reference = create_rgba_image("Reference", rgba)
    bpy.context.scene.anyimage_settings.color_reference = reference
    first = reference_cache.get_color_reference(reference)
    for color in [(0.1, 0.7, 0.2), (0.2, 0.1, 0.7)]:
        rgba[..., :3] = color
        reference.pixels.foreach_set(np.flipud(rgba).ravel())
        reference.update()
        second = reference_cache.get_color_reference(reference, refresh=True)
        assert second is not first
        np.testing.assert_allclose(image_rgba(second.image), rgba, atol=1/255)
        first = second


def test_byte_reference_is_encoded_once_and_palette_is_linear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_rgba_image("Reference", np.full((4, 4, 4), (.5, .2, .1, 1)))
    prepared = reference_cache.get_color_reference(reference)
    pixels = image_rgba(reference)[0, 0, :3]
    from anyimage.common.color_space import linear_rgb_to_oklab
    np.testing.assert_allclose(prepared.transfer.anchors, linear_rgb_to_oklab(prepared.colors), atol=1e-6)
    np.testing.assert_allclose(prepared.colors[0], srgb_to_linear_rgb(pixels), atol=.005)
