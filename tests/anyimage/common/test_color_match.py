"""Palette color transfer and independent lightness behavior."""

import numpy as np
import pytest

from anyimage.common.color_match import (
    ColorReference, _extract_color_palette, _merge_palette_colors, _transport_palette,
    apply_color_match, build_color_mapping, build_color_match,
    prepare_color_reference, resize_rgba_proxy,
)
from anyimage.common.color_space import linear_rgb_to_oklab


def _rgba(rgb, alpha=1.0):
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.concatenate((rgb, np.broadcast_to(alpha, rgb.shape[:-1])[..., None]), axis=-1).astype(np.float32)


def _match(reference, source, *, target_float=False):
    return build_color_match(build_color_mapping(reference, source), source, target_float=target_float)


def test_controls_are_independent_and_preserve_alpha_and_original():
    rng = np.random.default_rng(10)
    source = _rgba(rng.uniform(.2, .6, (10, 12, 3)), rng.random((10, 12)))
    original = source.copy()
    reference = _rgba(rng.uniform(.2, .6, (8, 8, 3)))
    match = _match(prepare_color_reference(reference), source, target_float=True)
    np.testing.assert_array_equal(apply_color_match(match, color=0, lightness=0), source)
    color_only = apply_color_match(match, color=1, lightness=0)
    lightness_only = apply_color_match(match, color=0, lightness=1)
    np.testing.assert_allclose(linear_rgb_to_oklab(color_only[..., :3])[..., 0], match.lab[..., 0], atol=1e-6)
    np.testing.assert_allclose(linear_rgb_to_oklab(lightness_only[..., :3])[..., 1:], match.lab[..., 1:], atol=1e-6)
    np.testing.assert_array_equal(color_only[..., 3], source[..., 3])
    np.testing.assert_array_equal(lightness_only[..., 3], source[..., 3])
    np.testing.assert_array_equal(source, original)
    np.testing.assert_array_equal(apply_color_match(match), apply_color_match(match, color=.5, lightness=0))


def test_reference_alpha_excludes_hidden_rgb():
    visible = _rgba([[[.8, .1, .05]]])
    hidden = np.concatenate((visible, _rgba([[[0, 0, 1]]], 0)), axis=1)
    target = _rgba(np.full((8, 8, 3), .25))
    a = apply_color_match(_match(prepare_color_reference(visible), target), color=1, lightness=1)
    b = apply_color_match(_match(prepare_color_reference(hidden), target), color=1, lightness=1)
    np.testing.assert_allclose(a, b, atol=1e-6)


@pytest.mark.parametrize("shape", [(1, 1), (8, 8)])
def test_constant_images_and_hidden_target_rgb(shape):
    reference = _rgba(np.full((*shape, 3), (.6, .25, .08)))
    source = _rgba(np.full((*shape, 3), (.05, .15, .5)), 0)
    result = apply_color_match(_match(prepare_color_reference(reference), source), color=1, lightness=1)
    np.testing.assert_allclose(result[..., :3], reference[..., :3], atol=.005)
    np.testing.assert_array_equal(result[..., 3], source[..., 3])


def test_lightness_curve_is_monotonic_and_matching_is_deterministic():
    gradient = np.broadcast_to(np.linspace(.1, .9, 100)[None, :, None], (4, 100, 3))
    reference = prepare_color_reference(_rgba(gradient ** 2))
    source = _rgba(gradient)
    a = apply_color_match(_match(reference, source), color=0, lightness=1)
    b = apply_color_match(_match(reference, source), color=0, lightness=1)
    assert np.isfinite(a).all()
    assert np.min(np.diff(linear_rgb_to_oklab(a[..., :3])[0, :, 0])) >= -1e-6
    np.testing.assert_array_equal(a, b)


def test_reference_area_weights_control_palette_transport():
    colors = np.asarray(((.8, .03, .01), (.01, .03, .8)), dtype=np.float32)
    anchors = linear_rgb_to_oklab(colors)
    balanced = ColorReference(colors, np.asarray((.5, .5)), np.zeros(9))
    weighted = ColorReference(colors, np.asarray((.25, .75)), np.zeros(9))
    source_weights = np.asarray((.5, .5))
    np.testing.assert_allclose(_transport_palette(anchors, source_weights, balanced), 0, atol=1e-6)
    delta = _transport_palette(anchors, source_weights, weighted)
    np.testing.assert_allclose(delta[0], (anchors[1, 1:] - anchors[0, 1:]) * .5, atol=1e-6)
    np.testing.assert_allclose(delta[1], 0, atol=1e-6)


def test_lightness_can_retain_hdr_range():
    reference = prepare_color_reference(_rgba([[[2, 3, 4]]]))
    target = _rgba([[[.1, .2, .3]]])
    floating = apply_color_match(_match(reference, target, target_float=True), color=0, lightness=1)
    assert np.isfinite(floating).all() and floating[..., :3].max() > 1
    byte = apply_color_match(_match(reference, target), color=0, lightness=1)
    assert byte[..., :3].max() <= 1


@pytest.mark.parametrize("invalid", [np.full((2, 2, 4), np.nan), np.empty((0, 1, 4)), np.ones((2, 2, 3))])
def test_invalid_pixels_are_rejected(invalid):
    with pytest.raises(ValueError):
        prepare_color_reference(invalid)
    with pytest.raises(ValueError):
        build_color_mapping(prepare_color_reference(np.ones((1, 1, 4))), invalid)


def test_empty_visible_reference_is_rejected():
    with pytest.raises(ValueError, match="no visible"):
        prepare_color_reference(np.zeros((2, 2, 4)))


def test_proxy_preserves_aspect_ratio():
    result = resize_rgba_proxy(np.ones((600, 1200, 4), dtype=np.float32))
    assert result.shape == (256, 512, 4)


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
    colors, _weights = _extract_color_palette(rgb.reshape(-1, 3))
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

    colors, weights = _extract_color_palette(rgb.reshape(-1, 3))

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
