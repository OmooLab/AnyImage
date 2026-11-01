"""Verify linear resampling and mixed byte/HDR Frame composition."""

from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from mathutils import Matrix

from anyimage.common.image import image_rgba
from anyimage.common.color_space import srgb_to_linear_rgb, linear_rgb_to_srgb
from anyimage.operators.frame_tool import operators


@pytest.fixture
def frame_context(monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    monkeypatch.setattr(operators, "frame_output_size", lambda *_: (1, 1))
    monkeypatch.setattr(operators, "configured_max_frame_resolution", lambda _: 2)
    monkeypatch.setattr(operators, "frame_result_transform", lambda *_: (Matrix.Identity(4), 2.0))
    yield SimpleNamespace(
        region=SimpleNamespace(width=2, height=2),
        region_data=SimpleNamespace(
            perspective_matrix=Matrix.Identity(4), view_matrix=Matrix.Identity(4),
            is_perspective=False,
        ),
    )
    bpy.ops.wm.read_factory_settings(use_empty=True)


def image_empty(rgba, *, floating=False, depth=1):
    image = bpy.data.images.new("Frame source", width=2, height=2, alpha=True, float_buffer=floating)
    image.colorspace_settings.name = "Linear Rec.709" if floating else "sRGB"
    image.alpha_mode = "STRAIGHT"
    pixels = np.asarray(np.broadcast_to(rgba, (2, 2, 4)), dtype=np.float32)
    image.pixels.foreach_set(np.flipud(pixels).ravel())
    obj = bpy.data.objects.new(image.name, None)
    obj.empty_display_type = "IMAGE"
    obj.empty_display_size = 2.0
    obj.data = image
    obj.matrix_world = Matrix.Translation((0, 0, -depth))
    bpy.context.collection.objects.link(obj)
    return obj


def apply(context, sources):
    context.active_object = sources[-1]
    result = operators.apply_frame(context, sources, ((0, 2), (2, 2), (2, 0), (0, 0)))
    return image_rgba(result.data)[0, 0]


def test_byte_resampling_averages_light_in_linear_space(frame_context):
    source = image_empty([[(0, 0, 0, 1), (1, 1, 1, 1)]])
    result = apply(frame_context, (source,))
    np.testing.assert_allclose(result, (*linear_rgb_to_srgb(np.full(3, .5)), 1), atol=1/255)


@pytest.mark.parametrize("floating_output", [False, True])
def test_mixed_byte_hdr_sources_use_active_image_encoding(frame_context, floating_output):
    byte = image_empty((.5, .25, 0, 1 if floating_output else .5), depth=2 if floating_output else 1)
    hdr = image_empty((1.5, .5, .25, .5 if floating_output else 1), floating=True,
                      depth=1 if floating_output else 2)
    byte_rgba, hdr_rgba = image_rgba(byte.data)[0, 0], image_rgba(hdr.data)[0, 0]
    byte_rgb = srgb_to_linear_rgb(byte_rgba[:3])
    if floating_output:
        sources = (byte, hdr)
        expected = hdr_rgba[:3] * hdr_rgba[3] + byte_rgb * (1 - hdr_rgba[3])
    else:
        sources = (hdr, byte)
        expected = linear_rgb_to_srgb(byte_rgb * byte_rgba[3] + hdr_rgba[:3] * (1 - byte_rgba[3]))
    result = apply(frame_context, sources)
    np.testing.assert_allclose(result, (*expected, 1), atol=1e-6 if floating_output else 1/255)
    assert sources[-1].data.is_float == floating_output
