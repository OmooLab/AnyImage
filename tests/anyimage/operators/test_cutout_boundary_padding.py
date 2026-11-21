"""Verify padded RGBA and reconstructed camera-space depth on Cutout boundaries."""

import bpy
import numpy as np
import pytest

from anyimage.operators.cutout_tool.boundary_padding import (
    apply_boundary_mapping, build_boundary_mapping, image_rgba_buffer, pad_cutout_images,
)


def test_color_samples_inside_outer_contour_hole_and_thin_strip():
    mask = np.zeros((17, 17), dtype=bool)
    mask[3:14, 3:14] = True
    mask[7:10, 7:10] = False
    y, x = np.indices(mask.shape, dtype=np.float32)
    rgba = np.stack((x, y, x+y, mask), axis=-1)
    apply_boundary_mapping(rgba, build_boundary_mapping(mask, 2, mask.shape))

    assert rgba[2, 8, 1] > 3 and rgba[7, 8, 1] < 7
    np.testing.assert_allclose(rgba[[2, 7], 8, 0], 8, atol=.5)
    np.testing.assert_allclose(rgba[[2, 7], 8, 3], 1)

    mask[:] = False
    mask[5:7, 2:13] = True
    mapping = build_boundary_mapping(mask, 4, mask.shape)
    rows, columns = np.rint(mapping.source).astype(int)
    assert len(rows) and mask[rows, columns].all()


@pytest.mark.parametrize("depth_size", [9, 18])
def test_color_and_depth_padding_preserve_boundaries_and_camera_rays(depth_size):
    mask = np.zeros((9, 9), dtype=bool)
    mask[2:7, 2:7] = True
    y, x = np.indices(mask.shape, dtype=np.float32)
    colors = np.stack((x, y, x+y, mask), axis=-1)
    dy, dx = np.indices((depth_size, depth_size), dtype=np.float32)
    depths = np.stack((dx, dy, dy+10, dy/depth_size), axis=-1)
    color = bpy.data.images.new("Cutout Color", 9, 9, alpha=True, float_buffer=True)
    depth = bpy.data.images.new("Cutout Depth", depth_size, depth_size, alpha=True, float_buffer=True)
    try:
        for image, pixels in ((color, colors), (depth, depths)):
            image.pixels.foreach_set(np.flipud(pixels).ravel())
        focal = center = depth_size // 2
        camera = ((focal, 0, center), (0, focal, center), (0, 0, 1))
        pad_cutout_images(color, depth, {"intrinsics": camera}, mask, 2)

        actual = image_rgba_buffer(color)
        assert actual[1, 4, 3] == 1
        np.testing.assert_array_equal(actual[4, 4], colors[4, 4])
        row = depth_size // 9
        px, py, z, validity = image_rgba_buffer(depth)[row, center]
        assert z > depths[row, center, 2] and validity > depths[row, center, 3]
        assert px == 0 and py == pytest.approx((row-center)/focal*z)
        assert color.packed_file and depth.packed_file
    finally:
        bpy.data.images.remove(color)
        bpy.data.images.remove(depth)
