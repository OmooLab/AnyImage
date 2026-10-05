"""Palette color transfer and independent lightness behavior."""

import numpy as np
import pytest

from anyimage.common.color_match import (
    ColorReference, _transport_palette, apply_color_match, build_color_match,
    prepare_color_reference, resize_rgba_proxy,
)
from anyimage.common.color_palette import extract_reference_palette
from anyimage.common.color_space import linear_rgb_to_oklab


def _rgba(rgb, alpha=1.0):
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.concatenate((rgb, np.broadcast_to(alpha, rgb.shape[:-1])[..., None]), axis=-1).astype(np.float32)


def _prepare(rgba):
    colors, weights = extract_reference_palette(rgba)
    return prepare_color_reference(rgba, colors, weights)


def test_controls_are_independent_and_preserve_alpha_and_original():
    rng = np.random.default_rng(10)
    source = _rgba(rng.uniform(.2, .6, (10, 12, 3)), rng.random((10, 12)))
    original = source.copy()
    reference = _rgba(rng.uniform(.2, .6, (8, 8, 3)))
    match = build_color_match(_prepare(reference), source, target_float=True)
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
    a = apply_color_match(build_color_match(_prepare(visible), target), color=1, lightness=1)
    b = apply_color_match(build_color_match(_prepare(hidden), target), color=1, lightness=1)
    np.testing.assert_allclose(a, b, atol=1e-6)


@pytest.mark.parametrize("shape", [(1, 1), (8, 8)])
def test_constant_images_and_hidden_target_rgb(shape):
    reference = _rgba(np.full((*shape, 3), (.6, .25, .08)))
    source = _rgba(np.full((*shape, 3), (.05, .15, .5)), 0)
    result = apply_color_match(build_color_match(_prepare(reference), source), color=1, lightness=1)
    np.testing.assert_allclose(result[..., :3], reference[..., :3], atol=.005)
    np.testing.assert_array_equal(result[..., 3], source[..., 3])


def test_lightness_curve_is_monotonic_and_matching_is_deterministic():
    gradient = np.broadcast_to(np.linspace(.1, .9, 100)[None, :, None], (4, 100, 3))
    reference = _prepare(_rgba(gradient ** 2))
    source = _rgba(gradient)
    a = apply_color_match(build_color_match(reference, source), color=0, lightness=1)
    b = apply_color_match(build_color_match(reference, source), color=0, lightness=1)
    assert np.isfinite(a).all()
    assert np.min(np.diff(linear_rgb_to_oklab(a[..., :3])[0, :, 0])) >= -1e-6
    np.testing.assert_array_equal(a, b)


def test_full_resolution_reuses_preview_mapping():
    rng = np.random.default_rng(11)
    reference = _prepare(_rgba(rng.random((8, 8, 3))))
    proxy = _rgba(rng.random((12, 16, 3)))
    preview = build_color_match(reference, proxy)
    full = np.repeat(np.repeat(proxy, 2, axis=0), 2, axis=1)
    match = build_color_match(reference, full, prepared_match=preview)
    expected = np.repeat(np.repeat(apply_color_match(preview, color=.7, lightness=.3), 2, axis=0), 2, axis=1)
    np.testing.assert_allclose(apply_color_match(match, color=.7, lightness=.3), expected, atol=1e-6)


def test_reference_area_weights_control_palette_transport():
    anchors = linear_rgb_to_oklab(np.asarray(((.8, .03, .01), (.01, .03, .8)), dtype=np.float32))
    balanced = ColorReference(anchors, np.asarray((.5, .5)), np.zeros(9))
    weighted = ColorReference(anchors, np.asarray((.25, .75)), np.zeros(9))
    source_weights = np.asarray((.5, .5))
    np.testing.assert_allclose(_transport_palette(anchors, source_weights, balanced), 0, atol=1e-6)
    delta = _transport_palette(anchors, source_weights, weighted)
    np.testing.assert_allclose(delta[0], (anchors[1, 1:] - anchors[0, 1:]) * .5, atol=1e-6)
    np.testing.assert_allclose(delta[1], 0, atol=1e-6)


def test_lightness_can_retain_hdr_range():
    reference = _prepare(_rgba([[[2, 3, 4]]]))
    target = _rgba([[[.1, .2, .3]]])
    floating = apply_color_match(build_color_match(reference, target, target_float=True), color=0, lightness=1)
    assert np.isfinite(floating).all() and floating[..., :3].max() > 1
    byte = apply_color_match(build_color_match(reference, target), color=0, lightness=1)
    assert byte[..., :3].max() <= 1


@pytest.mark.parametrize("invalid", [np.full((2, 2, 4), np.nan), np.empty((0, 1, 4)), np.ones((2, 2, 3))])
def test_invalid_pixels_are_rejected(invalid):
    with pytest.raises(ValueError):
        prepare_color_reference(invalid, np.ones((1, 3)), np.ones(1))
    with pytest.raises(ValueError):
        build_color_match(_prepare(np.ones((1, 1, 4))), invalid)


def test_empty_visible_reference_is_rejected():
    with pytest.raises(ValueError, match="no visible"):
        prepare_color_reference(np.zeros((2, 2, 4)), np.ones((1, 3)), np.ones(1))


def test_proxy_preserves_aspect_ratio():
    result = resize_rgba_proxy(np.ones((600, 1200, 4), dtype=np.float32))
    assert result.shape == (256, 512, 4)
