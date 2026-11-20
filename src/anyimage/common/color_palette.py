"""Select prominent display colors with Material's Celebi and Score algorithms."""

import numpy as np
from materialyoucolor.quantize import QuantizeCelebi
from materialyoucolor.score.score import Score, ScoreOptions

from .color_space import linear_rgb_to_oklab, linear_rgb_to_srgb, srgb_to_linear_rgb

_PALETTE_MERGE_DISTANCE = 0.06


def extract_color_palette(rgb):
    """Return prominent display colors and area weights from linear RGB samples."""
    srgb = linear_rgb_to_srgb(np.clip(rgb, 0.0, 1.0))
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
