import time

import numpy as np

from anyimage.common.color_match import match_color_reference, resize_rgba_proxy


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


def test_match_and_contrast_are_bounded_and_preserve_alpha():
    values = np.linspace(0.1, 0.8, 64, dtype=np.float32)
    target = _rgba(np.broadcast_to(values[None, :, None], (8, 64, 3)).copy(), 0.4)
    reference = _rgba(np.clip(target[..., :3] * 0.7 + 0.15, 0.0, 1.0))

    bounded = match_color_reference(reference, target, match=1.5, contrast=0.5)
    clipped = match_color_reference(reference, target, match=20.0, contrast=20.0)

    np.testing.assert_array_equal(bounded, clipped)
    np.testing.assert_array_equal(bounded[..., 3], target[..., 3])
    assert np.ptp(bounded[..., 0]) > np.ptp(
        match_color_reference(reference, target, contrast=0.0)[..., 0]
    )


def test_zero_match_keeps_color_when_preview_omits_final_dither():
    target = _rgba(np.full((8, 8, 3), (0.2, 0.4, 0.6), dtype=np.float32))
    reference = _rgba(np.full((8, 8, 3), (0.8, 0.2, 0.1), dtype=np.float32))

    result = match_color_reference(reference, target, match=0.0, preview=True)

    np.testing.assert_allclose(result, target, atol=2e-6)


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
