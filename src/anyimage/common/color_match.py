"""Smoothed HM-MKL-HM transfer and linear RGB blending.

Histogram matching and MKL adapted from color-matcher 0.6.0:
https://github.com/hahnec/color-matcher
Copyright (c) 2020 Christopher Hahne <info@christopherhahne.de>
SPDX-License-Identifier: GPL-3.0-or-later
Distributed without warranty; see the GNU General Public License in LICENSE.
"""

from typing import NamedTuple

import numpy as np
from scipy import ndimage

from .color_space import linear_rgb_to_srgb, srgb_to_linear_rgb

MIX_LIMITS = (0.0, 1.0)
PREVIEW_MAX_SIZE = 512
_REFERENCE_SAMPLES = 65_536
_HISTOGRAM_CURVE_SAMPLES = 2_048
_HISTOGRAM_SMOOTH_SIGMA = 0.025
_HISTOGRAM_MAX_SLOPE = 3.0


def resize_rgba_proxy(rgba, max_size=PREVIEW_MAX_SIZE):
    """Resize RGBA pixels to a bounded, aspect-preserving preview."""
    rgba = _require_rgba(rgba)
    height, width = rgba.shape[:2]
    longest = max(height, width)
    if longest <= max_size:
        return rgba.copy()
    scale = max_size / longest
    output_height = max(1, int(round(height * scale)))
    output_width = max(1, int(round(width * scale)))
    return ndimage.zoom(
        rgba,
        (output_height / height, output_width / width, 1.0),
        order=1,
        mode="nearest",
        prefilter=False,
    ).astype(np.float32, copy=False)


class ColorReference(NamedTuple):
    """Keep reference CDFs and Gaussian statistics in encoded RGB."""

    histograms: tuple
    mean: np.ndarray
    covariance: np.ndarray


class ColorMatch(NamedTuple):
    """Own the original RGBA and full-strength linear RGB result."""

    rgba: np.ndarray
    rgb: np.ndarray


def prepare_color_reference(rgba):
    """Prepare bounded alpha-weighted reference statistics once."""
    pixels = _require_rgba(rgba).reshape(-1, 4)
    cumulative = np.cumsum(np.clip(pixels[:, 3], 0.0, 1.0), dtype=np.float64)
    if cumulative[-1] <= 1e-8:
        raise ValueError("The color reference contains no visible pixels")
    if len(pixels) <= _REFERENCE_SAMPLES:
        weights = np.clip(pixels[:, 3], 0.0, 1.0).astype(np.float64)
        visible = weights > 0
        weights = weights[visible]
        samples = pixels[visible, :3]
    else:
        positions = (np.arange(_REFERENCE_SAMPLES) + 0.5) * (cumulative[-1] / _REFERENCE_SAMPLES)
        samples = pixels[np.searchsorted(cumulative, positions), :3]
        weights = np.ones(len(samples), dtype=np.float64)
    rgb = linear_rgb_to_srgb(samples).astype(np.float64)
    histograms = []
    for channel in rgb.T:
        values, inverse = np.unique(channel, return_inverse=True)
        counts = np.bincount(inverse, weights=weights)
        histograms.append((values, np.cumsum(counts) / weights.sum()))
    degrees = weights.sum() - np.dot(weights, weights) / weights.sum()
    covariance = (
        np.cov(rgb.T, aweights=weights)
        if degrees > np.finfo(np.float64).eps * weights.sum()
        else np.zeros((3, 3))
    )
    return ColorReference(tuple(histograms), np.average(rgb, axis=0, weights=weights), covariance)


def _smooth_histogram_match(rgb, reference):
    """Apply a continuous monotonic histogram curve to each RGB channel."""
    result = np.empty_like(rgb)
    for index, (values, cdf) in enumerate(reference.histograms):
        source, counts = np.unique(rgb[:, index], return_counts=True)
        source_cdf = np.cumsum(counts, dtype=np.float64) / len(rgb)
        mapped = np.interp(source_cdf, cdf, values)
        lower = min(0.0, float(source[0]))
        upper = max(1.0, float(source[-1]))
        grid = np.linspace(lower, upper, _HISTOGRAM_CURVE_SAMPLES)
        step = grid[1] - grid[0]
        curve = np.interp(grid, source, mapped)
        curve = ndimage.gaussian_filter1d(
            curve,
            _HISTOGRAM_SMOOTH_SIGMA / step,
            mode="nearest",
        )
        slope = np.clip(np.diff(curve) / step, 0.0, _HISTOGRAM_MAX_SLOPE)
        limited = np.concatenate(([0.0], np.cumsum(slope) * step))
        limited += np.mean(curve - limited)
        result[:, index] = np.interp(rgb[:, index], grid, limited)
    return result


def _mkl_matrix(source_covariance, reference_covariance):
    # Symmetric eigensolvers keep degenerate covariance matrices real.
    values, vectors = np.linalg.eigh(source_covariance)
    root = np.sqrt(np.maximum(values, 0.0))
    tolerance = max(float(root.max()) * 1e-10, np.finfo(np.float64).eps)
    inverse = np.divide(1.0, root, out=np.zeros_like(root), where=root > tolerance)
    middle = root[:, None] * (vectors.T @ reference_covariance @ vectors) * root[None, :]
    values, axes = np.linalg.eigh(middle)
    middle_root = (axes * np.sqrt(np.maximum(values, 0.0))) @ axes.T
    return vectors @ (inverse[:, None] * middle_root * inverse[None, :]) @ vectors.T


def build_color_match(reference, target_rgba, *, target_float=False):
    """Compute smoothed HM-MKL-HM without display-export normalization."""
    rgba = _require_rgba(target_rgba)
    rgb = linear_rgb_to_srgb(rgba[..., :3]).reshape(-1, 3).astype(np.float64)
    rgb = _smooth_histogram_match(rgb, reference)
    if len(rgb) > 1:
        matrix = _mkl_matrix(np.cov(rgb.T), reference.covariance)
        rgb = (rgb - rgb.mean(axis=0)) @ matrix.T + reference.mean
    else:
        rgb = np.broadcast_to(reference.mean, rgb.shape).copy()
    rgb = _smooth_histogram_match(rgb, reference)
    matched = srgb_to_linear_rgb(rgb.reshape(rgba.shape[:2] + (3,)))
    if not np.isfinite(matched).all():
        raise ValueError("Color matching produced invalid pixels")
    if not target_float:
        matched = np.clip(matched, 0.0, 1.0)
    return ColorMatch(rgba.copy(), matched)


def apply_color_match(match, mix=1.0):
    """Mix the original and matched linear RGB, preserving Alpha exactly."""
    if not np.isfinite(mix):
        raise ValueError("Mix must be finite")
    mix = float(np.clip(mix, *MIX_LIMITS))
    result = match.rgba.copy()
    if mix == 1.0:
        result[..., :3] = match.rgb
    elif mix != 0.0:
        result[..., :3] = match.rgba[..., :3] * (1.0 - mix) + match.rgb * mix
    return result


def _require_rgba(rgba):
    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or min(rgba.shape[:2]) <= 0:
        raise ValueError("Color matching requires a non-empty RGBA image")
    if not np.isfinite(rgba).all():
        raise ValueError("Color matching requires finite RGBA pixels")
    return rgba
