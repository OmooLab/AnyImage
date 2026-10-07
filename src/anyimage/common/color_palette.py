"""Select prominent display colors with Material's Celebi and Score algorithms."""

import numpy as np
from materialyoucolor.quantize import QuantizeCelebi
from materialyoucolor.score.score import Score, ScoreOptions

from .color_space import linear_rgb_to_oklab, linear_rgb_to_srgb, srgb_to_linear_rgb

_PALETTE_MERGE_DISTANCE = 0.06


def extract_reference_palette(rgba):
    """Return up to four prominent linear RGB colors and assigned area weights."""
    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[-1] != 4:
        raise ValueError("The color reference requires RGBA pixels")
    pixels = rgba.reshape((-1, 4))
    if not len(pixels) or not np.isfinite(pixels).all():
        raise ValueError("The color reference requires finite RGBA pixels")
    alpha = np.clip(pixels[:, 3], 0.0, 1.0)
    cumulative = np.cumsum(alpha, dtype=np.float64)
    if cumulative[-1] <= 1e-8:
        raise ValueError("The color reference contains no visible pixels")
    count = min(len(pixels), 16_384)
    positions = (np.arange(count) + 0.5) * (cumulative[-1] / count)
    rgb = np.clip(pixels[np.searchsorted(cumulative, positions), :3], 0.0, 1.0)
    srgb = linear_rgb_to_srgb(rgb)
    channels = np.rint(srgb * 255).astype(np.uint32)
    if np.all(channels == channels[:, :1]):
        levels, counts = np.unique(channels[:, 0], return_counts=True)
        populations = dict(zip((0xFF000000 | levels * 0x010101).tolist(), counts.tolist()))
    else:
        populations = QuantizeCelebi(channels.tolist(), 128)
    selected = Score.score(populations, ScoreOptions(desired=4, filter=False))
    candidates = np.asarray(list(populations), dtype=np.uint32)

    def linear_colors(argb):
        channels = (np.asarray(argb, dtype=np.uint32)[:, None] >> (16, 8, 0)) & 255
        values = channels.astype(np.float32) / 255.0
        return srgb_to_linear_rgb(values)

    colors = linear_colors(selected)
    distance = np.sum(
        (linear_rgb_to_oklab(linear_colors(candidates))[:, None, :]
         - linear_rgb_to_oklab(colors)[None, :, :]) ** 2,
        axis=2,
    )
    weights = np.bincount(
        np.argmin(distance, axis=1),
        weights=list(populations.values()),
        minlength=len(colors),
    )
    weights /= weights.sum()
    colors, weights = _merge_palette_colors(colors, weights)
    return colors.astype(np.float32), weights.astype(np.float32)


def _merge_palette_colors(colors, weights):
    """Merge perceptually close colors while retaining selected representatives."""
    lab = linear_rgb_to_oklab(colors)
    distances = np.linalg.norm(lab[:, None, :] - lab[None, :, :], axis=2)
    groups = [[index] for index in range(len(colors))]
    while len(groups) > 1:
        distance, first, second = min(
            (
                (float(distances[np.ix_(groups[first], groups[second])].max()), first, second)
                for first in range(len(groups))
                for second in range(first + 1, len(groups))
            ),
        )
        if distance >= _PALETTE_MERGE_DISTANCE:
            break
        groups[first].extend(groups.pop(second))
    representatives = [max(group, key=lambda index: weights[index]) for group in groups]
    merged_weights = np.asarray([weights[group].sum() for group in groups])
    return colors[representatives], merged_weights / merged_weights.sum()
