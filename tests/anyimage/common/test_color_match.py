"""Color transfer behavior and the upstream numerical baseline."""

import numpy as np
import pytest

from anyimage.common.color_match import (
    _HISTOGRAM_MAX_SLOPE,
    _smooth_histogram_match,
    apply_color_match,
    build_color_match,
    prepare_color_reference,
    resize_rgba_proxy,
)


def _rgba(rgb, alpha=1.0):
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.concatenate((rgb, np.broadcast_to(alpha, rgb.shape[:-1])[..., None]), axis=-1).astype(np.float32)


def test_smooth_histogram_curve_is_monotonic_and_slope_limited():
    source = np.linspace(0.0, 1.0, 4_096, dtype=np.float64)
    rgb = np.repeat(source[:, None], 3, axis=1)
    reference_rgb = np.zeros((100, 3), dtype=np.float32)
    reference_rgb[-5:] = 1.0
    reference = prepare_color_reference(_rgba(reference_rgb[None]))

    result = _smooth_histogram_match(rgb, reference)
    slope = np.diff(result[:, 0]) / np.diff(source)

    assert np.min(slope) >= -1e-10
    assert np.max(slope) <= _HISTOGRAM_MAX_SLOPE + 1e-3
    np.testing.assert_array_equal(result[:, 0], result[:, 1])


def test_mix_endpoints_and_intermediate_preserve_alpha_and_original():
    rng = np.random.default_rng(10)
    source = rng.random((10, 12, 4), dtype=np.float32)
    original = source.copy()
    reference = _rgba(rng.random((8, 8, 3), dtype=np.float32))
    match = build_color_match(prepare_color_reference(reference), source)
    np.testing.assert_array_equal(apply_color_match(match, 0), source)
    np.testing.assert_array_equal(apply_color_match(match, 1)[..., :3], match.rgb)
    mixed = apply_color_match(match, .25)
    np.testing.assert_array_equal(mixed[..., :3], source[..., :3] * .75 + match.rgb * .25)
    np.testing.assert_array_equal(mixed[..., 3], source[..., 3])
    np.testing.assert_array_equal(source, original)
    np.testing.assert_array_equal(apply_color_match(match, -1), source)
    np.testing.assert_array_equal(apply_color_match(match, 2), apply_color_match(match, 1))


def test_reference_alpha_excludes_hidden_rgb():
    visible = _rgba([[[.8,.1,.05]]])
    hidden = np.concatenate((visible, _rgba([[[0,0,1]]],0)), axis=1)
    target = _rgba(np.full((8,8,3),.25))
    np.testing.assert_array_equal(
        build_color_match(prepare_color_reference(visible),target).rgb,
        build_color_match(prepare_color_reference(hidden),target).rgb,
    )


def test_reference_alpha_weights_statistics():
    reference = _rgba([[[.1,.2,.3],[.8,.7,.6]]] * 10, [[1,.25]] * 10)
    prepared = prepare_color_reference(reference)
    assert prepared.histograms[0][1][0] == pytest.approx(.8)


@pytest.mark.parametrize('shape',[(1,1),(8,8)])
def test_constant_images_and_hidden_target_rgb(shape):
    reference = _rgba(np.full((*shape,3),(.6,.25,.08)))
    source = _rgba(np.full((*shape,3),(.05,.15,.5)), 0)
    match = build_color_match(prepare_color_reference(reference),source)
    np.testing.assert_allclose(match.rgb, reference[..., :3], atol=1e-6)
    np.testing.assert_array_equal(apply_color_match(match)[...,3], source[...,3])


def test_rank_deficient_gradient_is_finite_and_deterministic():
    gradient = np.broadcast_to(np.linspace(0,1,30)[None,:,None],(20,30,3))
    reference = prepare_color_reference(_rgba(gradient))
    source = _rgba(gradient[..., ::-1] * .8)
    a = build_color_match(reference,source)
    b = build_color_match(reference,source)
    assert np.isfinite(a.rgb).all()
    np.testing.assert_array_equal(a.rgb,b.rgb)


def test_float_reference_preserves_hdr_range_without_export_normalization():
    reference = prepare_color_reference(_rgba([[[2,3,4]]]))
    target = _rgba([[[.1,.2,.3]]])
    floating = build_color_match(reference,target,target_float=True)
    np.testing.assert_allclose(floating.rgb, [[[2,3,4]]], atol=2e-6)
    assert build_color_match(reference,target).rgb.max() <= 1


@pytest.mark.parametrize('invalid',[np.full((2,2,4),np.nan),np.empty((0,1,4)),np.ones((2,2,3))])
def test_invalid_pixels_are_rejected(invalid):
    with pytest.raises(ValueError):
        prepare_color_reference(invalid)
    with pytest.raises(ValueError):
        build_color_match(prepare_color_reference(np.ones((1,1,4))), invalid)


def test_empty_visible_reference_is_rejected():
    with pytest.raises(ValueError,match='no visible'):
        prepare_color_reference(np.zeros((2,2,4)))


def test_tiny_alpha_weight_does_not_produce_invalid_covariance():
    reference = prepare_color_reference(_rgba([[[.2,.3,.4],[.8,.7,.6]]], [[1,1e-30]]))
    assert np.isfinite(reference.covariance).all()


def test_proxy_preserves_aspect_ratio():
    result = resize_rgba_proxy(np.ones((600,1200,4),dtype=np.float32))
    assert result.shape == (256,512,4)
