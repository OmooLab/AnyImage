"""Verify exact image snapshots across precision and alpha conversions."""

import bpy
import numpy as np
import pytest

from anyimage.common import image as images


@pytest.mark.parametrize("space,alpha_mode", [
    ("Linear Rec.709", "STRAIGHT"),
    ("Linear Rec.709", "PREMUL"),
    ("Non-Color", "STRAIGHT"),
    ("sRGB", "STRAIGHT"),
])
def test_clean_float_snapshot_restores_pixels_after_byte_replacement(space, alpha_mode):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        source = bpy.data.images.new("Original.exr", width=4, height=1, alpha=True, float_buffer=True)
        source.colorspace_settings.name = space
        source.alpha_mode = alpha_mode
        source.pixels.foreach_set(np.array([[2, .4, 1, a] for a in (0, .25, .5, 1)], np.float32).ravel())
        source.update()
        source.pack()
        assert not source.is_dirty
        before = images.image_pixels(source)
        state = images.image_content_state(source)
        identity = (source.as_pointer(), source.name, source.filepath_raw)
        result = bpy.data.images.new("Replacement.png", width=2, height=2, alpha=True)
        result.colorspace_settings.name = "sRGB"
        result.alpha_mode = "PREMUL"
        result[images.COLOR_NORMALIZED_PROPERTY] = True
        result.pixels.foreach_set(np.tile([.2, .4, .6, 1], 4).astype(np.float32))
        result.pack()
        images.replace_image_content(source, result)
        assert not source.is_float and tuple(source.size) == (2, 2)
        assert source[images.COLOR_NORMALIZED_PROPERTY]
        np.testing.assert_array_equal(images.image_pixels(source), images.image_pixels(result))
        images.restore_image_content(source, state)
        assert (source.as_pointer(), source.name, source.filepath_raw) == identity
        assert source.is_float and tuple(source.size) == (4, 1)
        assert source.colorspace_settings.name == space and source.alpha_mode == alpha_mode
        assert bytes(source.packed_file.data) == state["packed"]
        assert not source.get(images.COLOR_NORMALIZED_PROPERTY)
        np.testing.assert_array_equal(images.image_pixels(source), before)
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)
