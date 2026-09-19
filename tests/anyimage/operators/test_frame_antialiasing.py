from unittest.mock import patch
import numpy as np
import pytest


from anyimage.common.image import premultiplied_rgba
from anyimage.operators.frame_tool import compositing as frame
from anyimage.operators.frame_tool.projection import frame_source_projection


def source(rgba, *, bounds=(-1, 1, -1, 1), depth=1, slope=0, active=True):
    rgba = np.asarray(rgba, dtype=np.float32)
    height, width = rgba.shape[:2]
    world = np.eye(4)
    world[2, 3] = -depth
    world[2, 0] = slope
    result = frame_source_projection(
        np.eye(4), np.eye(4), world, bounds, (1, 1), perspective=False
    )
    result.update(
        rgba=rgba, pixels=premultiplied_rgba(np.flipud(rgba).ravel(), (width, height)),
        image_size=(width, height), active=active, name="Active" if active else "Bottom",
    )
    return result


def render(sources, size=(1, 1)):
    return np.flipud(frame.composite_frame_pixels(
        sources, ((0, 1), (1, 1), (1, 0), (0, 0)), size
    ).reshape(size[1], size[0], 4))


def test_white_half_coverage_does_not_mix_canvas_black():
    image = source([[[1, 1, 1, 1]]], bounds=(-1, 0, -1, 1))
    np.testing.assert_allclose(render((image,)), [[[1, 1, 1, 0.5]]])


def test_uncovered_canvas_has_no_rgb_to_reveal_with_mask_add():
    from anyimage.common.selection import SelectionMask
    from anyimage.operators.mask_tool import apply_alpha_mask

    result = render((source([[[1, 1, 1, 1]]], bounds=(-0.5, 0.5, -0.5, 0.5)),), (8, 8))
    uncovered = result[..., 3] == 0
    assert np.any(uncovered)
    np.testing.assert_array_equal(result[uncovered], 0)
    restored = np.flipud(apply_alpha_mask(
        result, SelectionMask(np.ones((8, 8)), (0, 0, 8, 8)), "EXTEND"
    ).reshape((8, 8, 4)))
    np.testing.assert_array_equal(restored[..., :3][uncovered], 0)
    np.testing.assert_array_equal(restored[..., 3], 1)


def test_partial_foreground_over_transparent_blue():
    bottom = source([[[0, 0, 1, 0]]], depth=2, active=False)
    top = source([[[1, 0, 0, 0.5]]], bounds=(-1, 0, -1, 1))
    np.testing.assert_allclose(render((bottom, top)), [[[0.25, 0, 0.75, 0.25]]])


@pytest.mark.parametrize("alpha", [0, 1e-12, 1e-8, 1e-7])
def test_near_zero_alpha_keeps_covered_rgb(alpha):
    result = render((source([[[0.2, 0.4, 0.8, alpha]]]),))
    np.testing.assert_allclose(result[..., :3], [[[0.2, 0.4, 0.8]]])
    np.testing.assert_allclose(result[..., 3], 0 if alpha <= 1e-8 else alpha, atol=1e-15)


def test_narrow_source_missed_by_center_is_sampled():
    image = source([[[1, 1, 1, 1]]], bounds=(-0.8, -0.7, -1, 1))
    np.testing.assert_allclose(render((image,)), [[[1, 1, 1, 0.25]]])


@pytest.mark.parametrize("alpha", [0, 1])
def test_crossing_planes_resolve_per_sample_depth(alpha):
    first = source([[[1, 0, 0, alpha]]], slope=1)
    second = source([[[0, 0, 1, alpha]]], slope=-1, active=False)
    np.testing.assert_allclose(render((first, second)), [[[0.5, 0, 0.5, alpha]]])


def test_aligned_interior_keeps_checkerboard():
    rgba = np.ones((8, 8, 4), dtype=np.float32)
    rgba[..., :3] = (np.indices((8, 8)).sum(axis=0) % 2)[..., None]
    np.testing.assert_allclose(render((source(rgba),), (8, 8)), rgba)


def test_oblique_boundary_matches_reference_and_chunk_sizes():
    top = source([[[1, 0, 0, 0.5]]], bounds=(-0.7, 0.7, -0.7, 0.7))
    angle = 0.3
    world = np.eye(4)
    world[:2, :2] = ((np.cos(angle), -np.sin(angle)), (np.sin(angle), np.cos(angle)))
    world[2, 3] = -1
    top.update(frame_source_projection(
        np.eye(4), np.eye(4), world, (-0.7, 0.7, -0.7, 0.7), (1, 1), perspective=False
    ))
    bottom = source([[[0, 0, 1, 0]]], depth=2, active=False)
    sources = (bottom, top)
    size = 17
    reference = np.zeros((size, size, 4), dtype=np.float32)
    for dy in (0.125, 0.375, 0.625, 0.875):
        for dx in (0.125, 0.375, 0.625, 0.875):
            x, y = np.meshgrid((np.arange(size) + dx) / size, 1 - (np.arange(size) + dy) / size)
            sample, _ = frame._composite_frame_samples(sources, np.stack((x, y), axis=-1))
            reference += sample / 16
    for rows in (1, 3, 256):
        with patch.object(frame, "PROJECTIVE_CHUNK_ROWS", rows):
            np.testing.assert_allclose(render(sources, (size, size)), reference, atol=1e-6)


@pytest.mark.parametrize("background", [0, 1])
def test_packed_frame_mask_extend_keeps_boundary_color(background):
    from io import BytesIO
    import bpy
    from PIL import Image
    from anyimage.common.image import create_image_edit_result, image_rgba
    from anyimage.common.selection import SelectionMask
    from anyimage.operators.mask_tool import apply_alpha_mask

    bottom = source([[[background, background, background, 0]]], depth=2, active=False)
    top = source([[[1, 0, 0, 1]]], bounds=(-1, 0, -1, 1))
    rgba = render((bottom, top))
    original = bpy.data.images.new("Boundary source", width=1, height=1, alpha=True)
    result = create_image_edit_result(original, rgba.ravel(), (1, 1))
    try:
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
