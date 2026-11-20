import numpy as np
import pytest

from anyimage.common.color_match import prepare_color_reference
from anyimage.common.color_palette import extract_color_palette, _merge_palette_colors


def _rgba(rgb, alpha=1.0):
    rgb = np.asarray(rgb, dtype=np.float32)
    alpha = np.broadcast_to(np.asarray(alpha, dtype=np.float32), rgb.shape[:-1])
    return np.concatenate((rgb, alpha[..., None]), axis=-1)


@pytest.mark.parametrize("row", [501, 503])
def test_palette_keeps_a_thin_saturated_accent(row):
    rgb = np.full((1024, 1024, 3), 0.3, dtype=np.float32)
    rgb[row:row + 2, 200:800] = (1.0, 0.0, 0.0)

    reference = prepare_color_reference(_rgba(rgb))
    colors, weights = reference.colors, reference.weights

    assert np.min(np.linalg.norm(colors - (1.0, 0.0, 0.0), axis=1)) < 0.02
    np.testing.assert_allclose(weights.sum(), 1.0)


def test_palette_weights_follow_visible_area():
    rgba = _rgba(np.full((16, 16, 3), (0.9, 0.02, 0.01), dtype=np.float32))
    rgba[:, 8:, :3] = (0.01, 0.02, 0.9)
    rgba[:, 8:, 3] = 0.25

    reference = prepare_color_reference(rgba)
    colors, weights = reference.colors, reference.weights

    assert weights[np.argmax(colors[:, 0])] == pytest.approx(0.8, abs=0.02)


@pytest.mark.parametrize("levels,start,end", [(16, 0.1, 0.8), (256, 0.0, 1.0)])
def test_neutral_reference_does_not_produce_a_fallback_hue(levels, start, end):
    rgb = np.broadcast_to(np.linspace(start, end, levels)[None, :, None], (16, levels, 3))
    colors, _weights = extract_color_palette(rgb.reshape(-1, 3))
    assert np.max(np.ptp(colors, axis=1)) < 0.005


def test_reference_palette_ignores_transparency_and_is_deterministic():
    reference = _rgba(
        np.asarray([[[0.8, 0.1, 0.05], [0.0, 0.0, 1.0]]], dtype=np.float32),
        [[1.0, 0.0]],
    )

    first = prepare_color_reference(reference)
    second = prepare_color_reference(reference)

    np.testing.assert_array_equal(first.colors, second.colors)
    np.testing.assert_array_equal(first.weights, second.weights)
    assert first.colors.shape == (1, 3)
    np.testing.assert_allclose(first.colors[0], reference[0, 0, :3], atol=0.005)
    np.testing.assert_array_equal(first.weights, (1.0,))


def test_palette_selects_distinct_colors_close_to_source():
    rgb = np.empty((80, 120, 3), dtype=np.float32)
    for index, color in enumerate(
        (
            (0.5, 0.08, 0.12),
            (0.53, 0.09, 0.13),
            (0.04, 0.35, 0.48),
            (0.08, 0.5, 0.12),
            (0.65, 0.5, 0.05),
            (0.15, 0.08, 0.4),
        )
    ):
        rgb[:, index * 20 : (index + 1) * 20] = color

    colors, weights = extract_color_palette(rgb.reshape(-1, 3))

    assert 3 <= len(colors) <= 4
    np.testing.assert_allclose(weights.sum(), 1.0, atol=1e-6)
    source_colors = rgb.reshape((-1, 3))
    for color in colors:
        assert np.min(np.linalg.norm(source_colors - color, axis=1)) < 0.04


def test_close_dark_colors_merge_without_averaging_distinct_accents():
    colors = np.asarray(((.002, .003, .002), (.003, .004, .003), (.8, .02, .01)), dtype=np.float32)
    merged, weights = _merge_palette_colors(colors, np.asarray((.6, .35, .05)))
    np.testing.assert_array_equal(merged, colors[[0, 2]])
    np.testing.assert_allclose(weights, (.95, .05))
