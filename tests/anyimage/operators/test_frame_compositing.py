import unittest
from unittest.mock import patch

import numpy as np
import pytest

from anyimage.common import projective_image
from anyimage.operators.frame_tool import compositing
from anyimage.operators.frame_tool.projection import frame_source_projection


def frame_pixel_source(rgba, *, bounds=(-1, 1, -1, 1), depth=1, slope=0,
                      active=True, name="Active", region_size=None):
    rgba = np.asarray(rgba, dtype=np.float32)
    height, width = rgba.shape[:2]
    world = np.eye(4)
    world[2, 3] = -depth
    world[2, 0] = slope
    result = frame_source_projection(
        np.eye(4), np.eye(4), world, bounds, region_size or (width, height), perspective=False
    )
    result.update(
        rgba=rgba, pixels=projective_image.premultiplied_rgba(np.flipud(rgba).ravel(), (width, height)),
        image_size=(width, height), active=active, name=name,
    )
    return result


class FrameCompositingTest(unittest.TestCase):
    def test_frame_composites_far_to_near_and_breaks_ties_with_active_on_top(self):
        frame = ((0, 2), (2, 2), (2, 0), (0, 0))
        top = frame_pixel_source(np.tile((0, 0, 1, .5), (2, 2, 1)), depth=1)
        for depth in (1, 2):
            bottom = frame_pixel_source(np.tile((1, 0, 0, 1), (2, 2, 1)), depth=depth, active=False)
            result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
            np.testing.assert_allclose(result.reshape(-1, 4), np.tile((.5, 0, .5, 1), (4, 1)))

    def test_frame_composites_orthographic_samples_at_negative_depth(self):
        pixels = np.tile((.25, .5, .75, 1), (2, 2, 1)).astype(np.float32)
        source = frame_pixel_source(pixels, depth=-1)
        result = compositing.composite_frame_pixels((source,), ((0, 2), (2, 2), (2, 0), (0, 0)), (2, 2))
        np.testing.assert_array_equal(result.reshape(2, 2, 4), pixels)

    def test_frame_hidden_rgb_uses_bottom_valid_depth_and_stable_ties(self):
        blue = np.tile((0, 0, 1, 0), (2, 2, 1))
        red = np.tile((1, 0, 0, 0), (2, 2, 1))
        frame = ((0, 2), (2, 2), (2, 0), (0, 0))
        for depth in (2.0, 1.0, -1.0):
            with self.subTest(depth=depth):
                bottom = frame_pixel_source(blue, depth=depth, name="A", active=False)
                top = frame_pixel_source(red, depth=min(depth, 1.0))
                result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
                np.testing.assert_allclose(result.reshape((2, 2, 4)), blue)
        middle = frame_pixel_source(red, name="B", active=False)
        bottom = frame_pixel_source(blue, name="A", active=False)
        top = frame_pixel_source(red)
        result = compositing.composite_frame_pixels((middle, top, bottom), frame, (2, 2))
        np.testing.assert_allclose(result.reshape((2, 2, 4)), blue)
        bottom["screen_to_source"][0, 2] += 0.5
        result = np.flipud(compositing.composite_frame_pixels(
            (top, bottom), frame, (2, 2)
        ).reshape((2, 2, 4)))
        np.testing.assert_allclose(result[:, 0], blue[:, 0])
        np.testing.assert_allclose(result[:, 1], red[:, 1])
        bottom["perspective"] = True
        bottom["source_to_view"][2, 2] = 1.0
        result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
        np.testing.assert_allclose(result.reshape((2, 2, 4)), red)

    def test_frame_hidden_rgb_tracks_crossing_planes(self):
        bottom = frame_pixel_source(np.tile((0, 0, 1, 0), (2, 2, 1)), active=False)
        top = frame_pixel_source(np.tile((1, 0, 0, 0), (2, 2, 1)))
        bottom["source_to_view"][2] = (2, 0, -2)
        result = np.flipud(compositing.composite_frame_pixels(
            (top, bottom), ((0, 2), (2, 2), (2, 0), (0, 0)), (2, 2)
        ).reshape((2, 2, 4)))
        np.testing.assert_allclose(result[:, 0], np.tile((0, 0, 1, 0), (2, 1)))
        np.testing.assert_allclose(result[:, 1], np.tile((1, 0, 0, 0), (2, 1)))

    def test_frame_blends_rgb_over_bottom_color_with_independent_alpha(self):
        for bottom_alpha in (0.0, 0.5, 1.0):
            blue = np.tile((0, 0, 1, bottom_alpha), (2, 5, 1)).astype(np.float32)
            red = np.tile((1, 0, 0, 0), (2, 5, 1)).astype(np.float32)
            red[..., 3] = (0, 0.25, 0.5, 0.75, 1)
            sources = (frame_pixel_source(blue, depth=2, active=False),
                       frame_pixel_source(red))
            result = np.flipud(compositing.composite_frame_pixels(
                sources, ((0, 2), (5, 2), (5, 0), (0, 0)), (5, 2)
            ).reshape((2, 5, 4)))
            alpha = red[..., 3] + bottom_alpha * (1 - red[..., 3])
            expected = np.zeros_like(red)
            expected[..., 0] = red[..., 3]
            expected[..., 2] = 1 - red[..., 3]
            np.testing.assert_allclose(result[..., 3], alpha)
            np.testing.assert_allclose(result[..., :3], expected[..., :3])

    def test_frame_three_layers_preserve_foreground_gradient_over_white(self):
        white = np.tile((1, 1, 1, 0), (2, 6, 1)).astype(np.float32)
        red = np.tile((1, 0, 0, 0), (2, 6, 1)).astype(np.float32)
        red[..., 3] = (0, 0.01, 0.1, 0.25, 0.5, 1)
        blue = np.tile((0, 0, 1, 0.25), (2, 6, 1)).astype(np.float32)
        sources = (
            frame_pixel_source(white, depth=3, active=False),
            frame_pixel_source(red, depth=2, active=False),
            frame_pixel_source(blue),
        )
        result = np.flipud(compositing.composite_frame_pixels(
            sources, ((0, 2), (6, 2), (6, 0), (0, 0)), (6, 2)
        ).reshape((2, 6, 4)))
        red_alpha = red[..., 3:4]
        expected = ((red[..., :3] * red_alpha + 1 - red_alpha) * 0.75
                    + blue[..., :3] * 0.25)
        np.testing.assert_allclose(result[..., :3], expected)
        np.testing.assert_allclose(result[..., 3], 0.25 + red[..., 3] * 0.75)

    def test_frame_foreground_resampling_excludes_hidden_black(self):
        white = frame_pixel_source(
            np.tile((1, 1, 1, 0), (1, 2, 1)), depth=2, active=False
        )
        foreground = frame_pixel_source(
            np.asarray([[(1, 0, 0, 1), (0, 0, 0, 0)]])
        )
        result = compositing.composite_frame_pixels(
            (foreground, white), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(result, (1, 0.5, 0.5, 0.5))

    def test_frame_raw_sampling_and_empty_canvas_are_chunk_independent(self):
        rgba = np.tile((0, 1, 0, 0), (4, 4, 1)).astype(np.float32)
        rgba[1:3, 2:] = (1, 0, 0, 1)
        source = frame_pixel_source(rgba)
        frame = ((-3, 7), (7, 7), (7, -3), (-3, -3))
        results = []
        for rows in (1, 2, 256):
            with patch.object(compositing, "PROJECTIVE_CHUNK_ROWS", rows):
                results.append(np.flipud(compositing.composite_frame_pixels(
                    (source,), frame, (10, 10)
                ).reshape((10, 10, 4))))
        for result in results:
            np.testing.assert_array_equal(result, results[0])
            np.testing.assert_allclose(result[3:7, 3:7], rgba)
            np.testing.assert_array_equal(result[4, 7], 0)
            np.testing.assert_array_equal(result[0], 0)
        transparent = np.asarray([[(1, 0, 0, 0), (0, 0, 1, 0)]], dtype=np.float32)
        source = frame_pixel_source(transparent)
        framed = compositing.composite_frame_pixels(
            (source,), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(framed, (0.5, 0, 0.5, 0))
        sampled = projective_image.sample_rgba(
            transparent, np.asarray(((1, 0.5), (-1, 0.5)))
        )
        np.testing.assert_allclose(sampled, ((0.5, 0, 0.5, 0), (0, 0, 0, 0)))
        transparent[0, 0, 3] = 1
        source = frame_pixel_source(transparent)
        framed = compositing.composite_frame_pixels(
            (source,), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(framed, (0.5, 0, 0.5, 0.5))


def render(sources, size=(1, 1)):
    return np.flipud(compositing.composite_frame_pixels(
        sources, ((0, 1), (1, 1), (1, 0), (0, 0)), size
    ).reshape(size[1], size[0], 4))


def test_white_half_coverage_does_not_mix_canvas_black():
    image = frame_pixel_source([[[1, 1, 1, 1]]], bounds=(-1, 0, -1, 1))
    np.testing.assert_allclose(render((image,)), [[[1, 1, 1, 0.5]]])


def test_uncovered_canvas_has_no_rgb_to_reveal_with_mask_add():
    from anyimage.common.selection import SelectionMask
    from anyimage.operators.mask_tool import apply_alpha_mask

    result = render((frame_pixel_source([[[1, 1, 1, 1]]], bounds=(-0.5, 0.5, -0.5, 0.5)),), (8, 8))
    uncovered = result[..., 3] == 0
    assert np.any(uncovered)
    np.testing.assert_array_equal(result[uncovered], 0)
    restored = np.flipud(apply_alpha_mask(
        result, SelectionMask(np.ones((8, 8)), (0, 0, 8, 8)), "EXTEND"
    ).reshape((8, 8, 4)))
    np.testing.assert_array_equal(restored[..., :3][uncovered], 0)
    np.testing.assert_array_equal(restored[..., 3], 1)


def test_partial_foreground_over_transparent_blue():
    bottom = frame_pixel_source([[[0, 0, 1, 0]]], depth=2, active=False)
    top = frame_pixel_source([[[1, 0, 0, 0.5]]], bounds=(-1, 0, -1, 1))
    np.testing.assert_allclose(render((bottom, top)), [[[0.25, 0, 0.75, 0.25]]])


@pytest.mark.parametrize("alpha", [1e-8, 1e-7])
def test_near_zero_alpha_keeps_covered_rgb(alpha):
    result = render((frame_pixel_source([[[0.2, 0.4, 0.8, alpha]]]),))
    np.testing.assert_allclose(result[..., :3], [[[0.2, 0.4, 0.8]]])
    np.testing.assert_allclose(result[..., 3], 0 if alpha <= 1e-8 else alpha, atol=1e-15)


def test_narrow_source_missed_by_center_is_sampled():
    image = frame_pixel_source([[[1, 1, 1, 1]]], bounds=(-0.8, -0.7, -1, 1))
    np.testing.assert_allclose(render((image,)), [[[1, 1, 1, 0.25]]])


@pytest.mark.parametrize("alpha", [0, 1])
def test_crossing_planes_resolve_per_sample_depth(alpha):
    first = frame_pixel_source([[[1, 0, 0, alpha]]], slope=1)
    second = frame_pixel_source([[[0, 0, 1, alpha]]], slope=-1, active=False)
    np.testing.assert_allclose(render((first, second)), [[[0.5, 0, 0.5, alpha]]])


def test_aligned_interior_keeps_checkerboard():
    rgba = np.ones((8, 8, 4), dtype=np.float32)
    rgba[..., :3] = (np.indices((8, 8)).sum(axis=0) % 2)[..., None]
    np.testing.assert_allclose(render((frame_pixel_source(rgba, region_size=(1, 1)),), (8, 8)), rgba)


def test_oblique_boundary_matches_reference_and_chunk_sizes():
    top = frame_pixel_source([[[1, 0, 0, 0.5]]], bounds=(-0.7, 0.7, -0.7, 0.7))
    angle = 0.3
    world = np.eye(4)
    world[:2, :2] = ((np.cos(angle), -np.sin(angle)), (np.sin(angle), np.cos(angle)))
    world[2, 3] = -1
    top.update(frame_source_projection(
        np.eye(4), np.eye(4), world, (-0.7, 0.7, -0.7, 0.7), (1, 1), perspective=False
    ))
    bottom = frame_pixel_source([[[0, 0, 1, 0]]], depth=2, active=False)
    sources = (bottom, top)
    size = 17
    reference = np.zeros((size, size, 4), dtype=np.float32)
    for dy in (0.125, 0.375, 0.625, 0.875):
        for dx in (0.125, 0.375, 0.625, 0.875):
            x, y = np.meshgrid((np.arange(size) + dx) / size, 1 - (np.arange(size) + dy) / size)
            sample, _ = compositing._composite_frame_samples(sources, np.stack((x, y), axis=-1))
            reference += sample / 16
    for rows in (1, 3, 256):
        with patch.object(compositing, "PROJECTIVE_CHUNK_ROWS", rows):
            np.testing.assert_allclose(render(sources, (size, size)), reference, atol=1e-6)


@pytest.mark.parametrize("background", [0, 1])
def test_packed_frame_mask_extend_keeps_boundary_color(background):
    from io import BytesIO
    import bpy
    from PIL import Image
    from anyimage.common.image import create_image_edit_result, image_rgba
    from anyimage.common.selection import SelectionMask
    from anyimage.operators.mask_tool import apply_alpha_mask

    bottom = frame_pixel_source([[[background, background, background, 0]]], depth=2, active=False)
    top = frame_pixel_source([[[1, 0, 0, 1]]], bounds=(-1, 0, -1, 1))
    rgba = render((bottom, top))
    original = bpy.data.images.new("Boundary source", width=1, height=1, alpha=True)
    result = create_image_edit_result(original, rgba.ravel(), (1, 1))
    try:
        result.pack()
        packed = np.asarray(Image.open(BytesIO(result.packed_file.data))) / 255
        expected = (np.array([1, 0, 0]) + background) / 2
        np.testing.assert_allclose(packed[0, 0, :3], expected, atol=1 / 255)
        restored = apply_alpha_mask(
            image_rgba(result), SelectionMask(np.ones((1, 1)), (0, 0, 1, 1)), "EXTEND"
        ).reshape(1, 1, 4)
        np.testing.assert_allclose(restored[0, 0, :3], expected, atol=1 / 255)
        assert restored[0, 0, 3] == 1
        assert result.alpha_mode == "STRAIGHT"
    finally:
        bpy.data.images.remove(original)
        bpy.data.images.remove(result)
