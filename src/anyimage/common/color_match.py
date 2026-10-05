"""Palette-anchor chroma transfer with independent quantile lightness matching."""

from typing import NamedTuple

import numpy as np
from scipy import ndimage
from scipy.interpolate import PchipInterpolator
from scipy.optimize import linprog

from .color_palette import extract_reference_palette
from .color_space import linear_rgb_to_oklab, oklab_to_linear_rgb

COLOR_LIMITS = (0.0, 1.0)
LIGHTNESS_LIMITS = (0.0, 1.0)
PREVIEW_MAX_SIZE = 512
_ANALYSIS_SAMPLES = 16_384
_QUANTILES = np.asarray((0.0, 0.02, 0.08, 0.2, 0.5, 0.8, 0.92, 0.98, 1.0))


class ColorReference(NamedTuple):
    """Keep perceptual palette anchors, area weights and lightness quantiles."""

    anchors: np.ndarray
    weights: np.ndarray
    lightness: np.ndarray


class ColorMatch(NamedTuple):
    """Cache original perceptual pixels and independent adjustment fields."""

    rgba: np.ndarray
    lab: np.ndarray
    chroma_delta: np.ndarray
    lightness_delta: np.ndarray
    target_float: bool
    anchors: np.ndarray
    anchor_delta: np.ndarray
    source_lightness: np.ndarray


def resize_rgba_proxy(rgba, max_size=PREVIEW_MAX_SIZE):
    """Resize RGBA pixels to a bounded, aspect-preserving preview."""
    rgba = _require_rgba(rgba)
    height, width = rgba.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return rgba.copy()
    scale = max_size / longest
    return ndimage.zoom(
        rgba,
        (max(1, round(height * scale)) / height,
         max(1, round(width * scale)) / width, 1.0),
        order=1, mode="nearest", prefilter=False,
    ).astype(np.float32, copy=False)


def _weighted_quantiles(values, weights):
    valid = weights > 0
    values, weights = values[valid], weights[valid]
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cumulative = (np.cumsum(weights) - 0.5 * weights) / weights.sum()
    return np.interp(_QUANTILES, cumulative, values)


def prepare_color_reference(rgba, colors, weights):
    """Prepare visible reference lightness using the displayed palette anchors."""
    pixels = _require_rgba(rgba).reshape(-1, 4)
    alpha = np.clip(pixels[:, 3], 0.0, 1.0)
    cumulative = np.cumsum(alpha, dtype=np.float64)
    if cumulative[-1] <= 1e-8:
        raise ValueError("The color reference contains no visible pixels")
    count = min(len(pixels), _ANALYSIS_SAMPLES)
    positions = (np.arange(count) + 0.5) * cumulative[-1] / count
    samples = pixels[np.searchsorted(cumulative, positions), :3]
    lightness = linear_rgb_to_oklab(samples)[:, 0]
    return ColorReference(
        linear_rgb_to_oklab(colors), np.asarray(weights, dtype=np.float64),
        _weighted_quantiles(lightness, np.ones(count)),
    )


def _transport_palette(anchors, weights, reference):
    count, reference_count = len(anchors), len(reference.anchors)
    weights = np.asarray(weights, dtype=np.float64)
    weights /= weights.sum()
    reference_weights = reference.weights / reference.weights.sum()
    source_chroma = anchors[:, 1:]
    reference_chroma = reference.anchors[:, 1:]
    source_mean = weights @ source_chroma
    reference_mean = reference_weights @ reference_chroma
    cost = np.sum(
        ((source_chroma - source_mean)[:, None, :]
         - (reference_chroma - reference_mean)[None, :, :]) ** 2, axis=2,
    )
    source_rank = np.argsort(np.argsort(anchors[:, 0])) / max(count - 1, 1)
    reference_rank = np.argsort(np.argsort(reference.anchors[:, 0])) / max(reference_count - 1, 1)
    cost += 0.015 * (source_rank[:, None] - reference_rank[None, :]) ** 2
    equalities = np.concatenate((
        np.repeat(np.eye(count), reference_count, axis=1),
        np.tile(np.eye(reference_count), (1, count)),
    ))
    result = linprog(
        cost.ravel(), A_eq=equalities,
        b_eq=np.concatenate((weights, reference_weights)),
        bounds=(0.0, None), method="highs",
    )
    if not result.success:
        raise RuntimeError("Unable to match color palette anchors")
    mapped = result.x.reshape(count, reference_count) @ reference_chroma
    return (mapped / np.maximum(weights[:, None], 1e-8) - source_chroma).astype(np.float32)


def build_color_match(reference, target_rgba, *, target_float=False, prepared_match=None):
    """Prepare palette chroma and the original nine-point lightness curve once."""
    rgba = _require_rgba(target_rgba)
    if prepared_match is None:
        samples = rgba.reshape(-1, 4)
        indices = np.linspace(0, len(samples) - 1, min(len(samples), _ANALYSIS_SAMPLES), dtype=np.intp)
        samples = samples[indices].copy()
        samples[:, 3] = 1.0
        colors, weights = extract_reference_palette(samples.reshape(1, -1, 4))
        anchors = linear_rgb_to_oklab(colors)
        delta = _transport_palette(anchors, weights, reference)
        source_quantiles = _weighted_quantiles(
            linear_rgb_to_oklab(samples[:, :3])[:, 0], np.ones(len(samples)),
        )
    else:
        anchors = prepared_match.anchors
        delta = prepared_match.anchor_delta
        source_quantiles = prepared_match.source_lightness
    lab = linear_rgb_to_oklab(rgba[..., :3])
    flat = lab.reshape(-1, 3)
    chroma_delta = np.empty((len(flat), 2), dtype=np.float32)
    for start in range(0, len(flat), 65_536):
        chunk = flat[start:start + 65_536]
        distance = np.sum((chunk[:, None, 1:] - anchors[None, :, 1:]) ** 2, axis=2)
        distance += 0.1 * (chunk[:, None, 0] - anchors[None, :, 0]) ** 2
        distance -= distance.min(axis=1, keepdims=True)
        membership = np.exp(-distance / (2 * 0.085**2))
        membership /= membership.sum(axis=1, keepdims=True)
        chroma_delta[start:start + len(chunk)] = membership @ delta
    source = source_quantiles
    keep = np.concatenate(([True], np.diff(source) > 1e-6))
    source, destination = source[keep], reference.lightness[keep]
    values = lab[..., 0]
    if len(source) == 1:
        lightness_delta = np.full_like(values, destination[0] - source[0])
    else:
        curve = PchipInterpolator(source, destination, extrapolate=False)
        mapped = curve(np.clip(values, source[0], source[-1])).astype(np.float32)
        mapped = np.where(values < source[0], values + destination[0] - source[0], mapped)
        mapped = np.where(values > source[-1], values + destination[-1] - source[-1], mapped)
        lightness_delta = mapped - values
    return ColorMatch(
        rgba.copy(), lab, chroma_delta.reshape(lab.shape[:2] + (2,)),
        lightness_delta, target_float, anchors, delta, source_quantiles,
    )


def apply_color_match(match, *, color=0.5, lightness=0.0):
    """Mix chroma and lightness independently, preserving original Alpha."""
    if not np.isfinite((color, lightness)).all():
        raise ValueError("Color and lightness must be finite")
    color = float(np.clip(color, *COLOR_LIMITS))
    lightness = float(np.clip(lightness, *LIGHTNESS_LIMITS))
    result = match.rgba.copy()
    if color == 0.0 and lightness == 0.0:
        return result
    lab = match.lab.copy()
    lab[..., 1:] += color * match.chroma_delta
    lab[..., 0] += lightness * match.lightness_delta
    rgb = oklab_to_linear_rgb(lab)
    result[..., :3] = rgb if match.target_float else np.clip(rgb, 0.0, 1.0)
    return result


def _require_rgba(rgba):
    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or min(rgba.shape[:2]) <= 0:
        raise ValueError("Color matching requires a non-empty RGBA image")
    if not np.isfinite(rgba).all():
        raise ValueError("Color matching requires finite RGBA pixels")
    return rgba
