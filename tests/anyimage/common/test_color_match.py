import time

import numpy as np

from anyimage.common.color_match import (
    extract_color_signature,
    linear_rgb_to_oklab,
    extract_reference_palette,
    match_color_reference,
    oklab_to_linear_rgb,
    resize_rgba_proxy,
)


def _rgba(rgb, alpha=1.0):
    rgb = np.asarray(rgb, dtype=np.float32)
    alpha = np.broadcast_to(np.asarray(alpha, dtype=np.float32), rgb.shape[:-1])
    return np.concatenate((rgb, alpha[..., None]), axis=-1)


def test_reference_alpha_ignores_hidden_rgb():
    reference = _rgba(
        np.asarray([[[0.8, 0.1, 0.05], [0.0, 0.0, 1.0]]], dtype=np.float32),
        [[1.0, 0.0]],
    )
    equivalent = _rgba(
        np.asarray([[[0.8, 0.1, 0.05], [0.8, 0.1, 0.05]]], dtype=np.float32),
        [[1.0, 0.0]],
    )
    target = _rgba(np.full((8, 8, 3), 0.25, dtype=np.float32))

    first = match_color_reference(reference, target)
    second = match_color_reference(equivalent, target)

    np.testing.assert_array_equal(first, second)


def test_target_hidden_rgb_is_matched_while_alpha_is_preserved():
    reference = _rgba(np.full((8, 8, 3), (0.6, 0.25, 0.08), dtype=np.float32))
    target_rgb = np.full((8, 8, 3), (0.05, 0.15, 0.5), dtype=np.float32)
    alpha = np.linspace(0.0, 1.0, 64, dtype=np.float32).reshape((8, 8))
    target = _rgba(target_rgb, alpha)

    result = match_color_reference(reference, target)

    np.testing.assert_array_equal(result[..., 3], alpha)
    assert not np.allclose(result[0, 0, :3], target[0, 0, :3])
    assert np.isfinite(result).all()


def test_match_is_deterministic_and_bounded_for_byte_images():
    y, x = np.mgrid[:32, :32]
    reference = _rgba(
        np.stack((0.2 + x / 64, 0.08 + y / 96, 0.04 + x / 128), axis=-1)
    )
    target = _rgba(
        np.stack((0.05 + y / 64, 0.1 + x / 96, 0.3 + y / 96), axis=-1)
    )

    first = match_color_reference(reference, target)
    second = match_color_reference(reference, target)

    np.testing.assert_array_equal(first, second)
    assert first[..., :3].min() >= 0.0
    assert first[..., :3].max() <= 1.0


def test_smooth_gradient_does_not_gain_large_steps():
    values = np.linspace(0.05, 0.95, 256, dtype=np.float32)
    target_rgb = np.broadcast_to(values[None, :, None], (16, 256, 3)).copy()
    reference_rgb = target_rgb * np.asarray((0.7, 0.55, 0.3), dtype=np.float32)
    result = match_color_reference(_rgba(reference_rgb), _rgba(target_rgb))

    adjacent = np.abs(np.diff(result[8, :, :3], axis=0))
    assert float(adjacent.max()) < 0.03
    assert len(np.unique(np.round(result[8, :, 0] * 255))) > 96


def test_compressed_edge_noise_is_not_amplified():
    height, width = 64, 128
    base = np.empty((height, width, 3), dtype=np.float32)
    base[:, :64] = (0.18, 0.2, 0.22)
    base[:, 64:] = (0.65, 0.62, 0.58)
    noise = ((np.indices((height, width)).sum(axis=0) % 2) * 2 - 1) * 0.006
    target_rgb = np.clip(base + noise[..., None], 0.0, 1.0)
    reference_rgb = np.clip(
        base * np.asarray((0.9, 0.72, 0.45), dtype=np.float32) + 0.03,
        0.0,
        1.0,
    )

    result = match_color_reference(_rgba(reference_rgb), _rgba(target_rgb))

    for source_region, result_region in (
        (target_rgb[:, :60], result[:, :60, :3]),
        (target_rgb[:, 68:], result[:, 68:, :3]),
    ):
        source_noise = np.std(np.diff(source_region, axis=1))
        result_noise = np.std(np.diff(result_region, axis=1))
        assert result_noise < source_noise * 1.15


def test_constant_and_nearly_degenerate_colors_remain_finite():
    reference = _rgba(np.full((12, 12, 3), (0.3, 0.3, 0.3), dtype=np.float32))
    target = _rgba(np.full((12, 12, 3), (0.2, 0.2, 0.2), dtype=np.float32))
    target[0, 0, 0] += 1e-6

    result = match_color_reference(reference, target)

    assert np.isfinite(result).all()
    np.testing.assert_array_equal(result[..., 3], target[..., 3])


def test_float_output_keeps_float_range_and_alpha():
    reference = _rgba(np.full((8, 8, 3), (2.0, 0.5, 0.2), dtype=np.float32))
    target = _rgba(np.full((8, 8, 3), (1.5, 0.3, 0.1), dtype=np.float32), 0.4)

    result = match_color_reference(reference, target, target_float=True)

    assert result[..., :3].max() > 1.0
    np.testing.assert_array_equal(result[..., 3], target[..., 3])


def test_color_and_lightness_are_bounded_and_preserve_alpha():
    values = np.linspace(0.1, 0.8, 64, dtype=np.float32)
    target = _rgba(np.broadcast_to(values[None, :, None], (8, 64, 3)).copy(), 0.4)
    reference = _rgba(np.clip(target[..., :3] * 0.7 + 0.15, 0.0, 1.0))

    bounded = match_color_reference(reference, target, color=1.0, lightness=1.0)
    clipped = match_color_reference(reference, target, color=20.0, lightness=20.0)

    np.testing.assert_array_equal(bounded, clipped)
    np.testing.assert_array_equal(bounded[..., 3], target[..., 3])


def test_reference_palette_ignores_transparency_and_is_deterministic():
    reference = _rgba(
        np.asarray([[[0.8, 0.1, 0.05], [0.0, 0.0, 1.0]]], dtype=np.float32),
        [[1.0, 0.0]],
    )

    first_colors, first_weights = extract_reference_palette(reference)
    second_colors, second_weights = extract_reference_palette(reference)

    np.testing.assert_array_equal(first_colors, second_colors)
    np.testing.assert_array_equal(first_weights, second_weights)
    assert first_colors.shape == (1, 3)
    np.testing.assert_allclose(first_colors[0], reference[0, 0, :3], atol=2e-5)
    np.testing.assert_array_equal(first_weights, (1.0,))


def test_spatial_signature_keeps_a_small_coherent_accent():
    rgb = np.full((80, 120, 3), (0.55, 0.35, 0.18), dtype=np.float32)
    accent = np.asarray((0.02, 0.5, 0.42), dtype=np.float32)
    rgb[52:68, 18:52] = accent

    signature = extract_color_signature(_rgba(rgb), alpha_weighted=True)
    signature_rgb = np.clip(oklab_to_linear_rgb(signature.colors), 0.0, 1.0)

    assert np.min(np.linalg.norm(signature_rgb - accent, axis=1)) < 0.08


def test_signature_anchor_count_adapts_and_stays_bounded():
    simple = np.empty((64, 64, 3), dtype=np.float32)
    simple[:32, :32] = (0.05, 0.12, 0.3)
    simple[:32, 32:] = (0.6, 0.2, 0.08)
    simple[32:, :32] = (0.1, 0.5, 0.2)
    simple[32:, 32:] = (0.7, 0.65, 0.4)
    complex_rgb = np.empty((96, 96, 3), dtype=np.float32)
    colors = np.linspace(0.04, 0.9, 48, dtype=np.float32).reshape((16, 3))
    for index, color in enumerate(colors):
        row, column = divmod(index, 4)
        complex_rgb[row * 24 : (row + 1) * 24, column * 24 : (column + 1) * 24] = color

    simple_signature = extract_color_signature(_rgba(simple), alpha_weighted=False)
    complex_signature = extract_color_signature(
        _rgba(complex_rgb),
        alpha_weighted=False,
    )

    assert len(simple_signature.colors) < len(complex_signature.colors)
    assert len(complex_signature.colors) <= 16


def test_unequal_signature_counts_match_deterministically():
    reference = np.empty((72, 72, 3), dtype=np.float32)
    reference[:, :24] = (0.7, 0.08, 0.16)
    reference[:, 24:48] = (0.04, 0.45, 0.5)
    reference[:, 48:] = (0.6, 0.55, 0.12)
    values = np.linspace(0.05, 0.8, 96, dtype=np.float32)
    target = np.stack(
        np.broadcast_arrays(values[None, :], values[:, None], 0.25),
        axis=-1,
    )
    reference_rgba = _rgba(reference)
    target_rgba = _rgba(target)
    reference_count = len(
        extract_color_signature(reference_rgba, alpha_weighted=True).colors
    )
    target_count = len(
        extract_color_signature(target_rgba, alpha_weighted=False).colors
    )

    first = match_color_reference(reference_rgba, target_rgba, preview=True)
    second = match_color_reference(reference_rgba, target_rgba, preview=True)

    assert reference_count != target_count
    np.testing.assert_array_equal(first, second)
    assert np.isfinite(first).all()


def test_dynamic_palette_merges_similar_anchors_and_uses_real_colors():
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

    colors, weights = extract_reference_palette(_rgba(rgb))

    assert 3 <= len(colors) <= 7
    np.testing.assert_allclose(weights.sum(), 1.0, atol=1e-6)
    source_colors = rgb.reshape((-1, 3))
    for color in colors:
        assert np.min(np.linalg.norm(source_colors - color, axis=1)) < 2e-5


def test_small_saturated_accent_survives_signature_and_palette():
    y, x = np.mgrid[:128, :128]
    rgb = np.stack(
        (
            0.12 + x / 1024,
            0.24 + y / 768,
            0.18 + x / 1536,
        ),
        axis=-1,
    ).astype(np.float32)
    accent = np.asarray((0.8, 0.015, 0.01), dtype=np.float32)
    rgb[74:80, 46:52] = accent
    rgba = _rgba(rgb)

    signature = extract_color_signature(rgba, alpha_weighted=True)
    signature_rgb = np.clip(oklab_to_linear_rgb(signature.colors), 0.0, 1.0)
    palette, _weights = extract_reference_palette(rgba)

    assert np.min(np.linalg.norm(signature_rgb - accent, axis=1)) < 0.12
    assert np.min(np.linalg.norm(palette - accent, axis=1)) < 0.12


def test_zero_color_and_lightness_keep_pixels_when_preview_omits_final_dither():
    target = _rgba(np.full((8, 8, 3), (0.2, 0.4, 0.6), dtype=np.float32))
    reference = _rgba(np.full((8, 8, 3), (0.8, 0.2, 0.1), dtype=np.float32))

    result = match_color_reference(
        reference, target, color=0.0, lightness=0.0, preview=True
    )

    np.testing.assert_allclose(result, target, atol=2e-6)


def test_color_and_lightness_transfer_independently():
    target = _rgba(np.full((8, 8, 3), (0.2, 0.4, 0.6), dtype=np.float32))
    reference = _rgba(np.full((8, 8, 3), (0.7, 0.25, 0.1), dtype=np.float32))
    target_lab = linear_rgb_to_oklab(target[..., :3])

    lightness_only = match_color_reference(
        reference, target, color=0.0, lightness=1.0, preview=True
    )
    color_only = match_color_reference(
        reference, target, color=1.0, lightness=0.0, preview=True
    )

    np.testing.assert_allclose(
        linear_rgb_to_oklab(lightness_only[..., :3])[..., 1:],
        target_lab[..., 1:],
        atol=2e-5,
    )
    np.testing.assert_allclose(
        linear_rgb_to_oklab(color_only[..., :3])[..., 0],
        target_lab[..., 0],
        atol=2e-5,
    )


def test_proxy_resize_preserves_aspect_ratio_and_bounds():
    source = _rgba(np.zeros((800, 1200, 3), dtype=np.float32))

    proxy = resize_rgba_proxy(source)

    assert proxy.shape == (341, 512, 4)
    assert proxy.dtype == np.float32


def test_megapixel_match_stays_in_interactive_range():
    height, width = 768, 1024
    x = np.linspace(0.05, 0.8, width, dtype=np.float32)
    y = np.linspace(0.05, 0.7, height, dtype=np.float32)
    target = _rgba(
        np.stack(np.broadcast_arrays(x[None, :], y[:, None], 0.3 + x[None, :] * 0.2), axis=-1)
    )
    reference = _rgba(target[::3, ::3, :3] * np.asarray((0.8, 0.65, 0.35), dtype=np.float32))

    started = time.perf_counter()
    result = match_color_reference(reference, target)
    elapsed = time.perf_counter() - started

    assert result.shape == target.shape
    assert elapsed < 5.0
