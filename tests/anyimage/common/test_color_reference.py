import bpy
import numpy as np
from anyimage.common import color_reference as reference_cache
from anyimage.common.image import image_rgba
from anyimage.common.color_space import srgb_to_linear_rgb
from tests.support.color_reference import create_clipboard_image, registered_color_reference, isolate_reference_cache


def test_reference_cache_refreshes_consecutive_pixel_edits(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rgba = np.full((4, 4, 4), (0.7, 0.2, 0.1, 1.0), dtype=np.float32)
    reference = create_clipboard_image("Reference", rgba)
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
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.5, .2, .1, 1)))
    prepared = reference_cache.get_color_reference(reference)
    pixels = image_rgba(reference)[0, 0, :3]
    np.testing.assert_allclose(prepared.transfer.colors[0], srgb_to_linear_rgb(pixels), atol=.005)
