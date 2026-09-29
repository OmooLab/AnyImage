"""Deterministic perceptual color matching for RGBA images."""

import numpy as np
from scipy import ndimage
from scipy.interpolate import PchipInterpolator


_ANALYSIS_SAMPLES = 65_536
_QUANTILES = np.asarray((0.0, 0.02, 0.08, 0.2, 0.5, 0.8, 0.92, 0.98, 1.0))
_LUMINANCE_INFLUENCE = 0.5
_CHROMA_INFLUENCE = 0.95
_CHROMA_SCALE_LIMITS = (0.6, 1.65)
_COVARIANCE_REGULARIZATION = 4e-4
_ADJUSTMENT_SIGMA = 2.0
MATCH_LIMITS = (0.0, 1.5)
CONTRAST_LIMITS = (-0.5, 0.5)
PREVIEW_MAX_SIZE = 512

_RGB_TO_LMS = np.asarray(
    (
        (0.4122214708, 0.2119034982, 0.0883024619),
        (0.5363325363, 0.6806995451, 0.2817188376),
        (0.0514459929, 0.1073969566, 0.6299787005),
    ),
    dtype=np.float32,
)
_LMS_TO_OKLAB = np.asarray(
    (
        (0.2104542553, 1.9779984951, 0.0259040371),
        (0.7936177850, -2.4285922050, 0.7827717662),
        (-0.0040720468, 0.4505937099, -0.8086757660),
    ),
    dtype=np.float32,
)
_OKLAB_TO_LMS = np.asarray(
    (
        (1.0, 1.0, 1.0),
        (0.3963377774, -0.1055613458, -0.0894841775),
        (0.2158037573, -0.0638541728, -1.2914855480),
    ),
    dtype=np.float32,
)
_LMS_TO_RGB = np.asarray(
    (
        (4.0767416621, -1.2684380046, -0.0041960863),
        (-3.3077115913, 2.6097574011, -0.7034186147),
        (0.2309699292, -0.3413193965, 1.7076147010),
    ),
    dtype=np.float32,
)
_BAYER_8 = np.asarray(
    (
        (0, 32, 8, 40, 2, 34, 10, 42),
        (48, 16, 56, 24, 50, 18, 58, 26),
        (12, 44, 4, 36, 14, 46, 6, 38),
        (60, 28, 52, 20, 62, 30, 54, 22),
        (3, 35, 11, 43, 1, 33, 9, 41),
        (51, 19, 59, 27, 49, 17, 57, 25),
        (15, 47, 7, 39, 13, 45, 5, 37),
        (63, 31, 55, 23, 61, 29, 53, 21),
    ),
    dtype=np.float32,
)


def linear_rgb_to_oklab(rgb):
    """Convert linear Rec.709 RGB values to OKLab."""
    rgb = np.asarray(rgb, dtype=np.float32)
    return np.cbrt(rgb @ _RGB_TO_LMS) @ _LMS_TO_OKLAB


def oklab_to_linear_rgb(lab):
    """Convert OKLab values to linear Rec.709 RGB."""
    lab = np.asarray(lab, dtype=np.float32)
    lms = lab @ _OKLAB_TO_LMS
    return (lms * lms * lms) @ _LMS_TO_RGB


def sample_rgba(rgba, max_samples=_ANALYSIS_SAMPLES):
    """Return an evenly distributed sample without resizing image content."""
    rgba = _require_rgba(rgba)
    height, width = rgba.shape[:2]
    if height * width <= max_samples:
        return rgba.reshape((-1, 4)).copy()
    ratio = width / height
    sample_width = min(width, max(1, int(round(np.sqrt(max_samples * ratio)))))
    sample_height = min(height, max(1, max_samples // sample_width))
    rows = np.linspace(0, height - 1, sample_height, dtype=np.intp)
    columns = np.linspace(0, width - 1, sample_width, dtype=np.intp)
    return rgba[np.ix_(rows, columns)].reshape((-1, 4)).copy()


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


def match_color_reference(
    reference_rgba,
    target_rgba,
    *,
    target_float=False,
    match=1.0,
    contrast=0.0,
    preview=False,
):
    """Match all target RGB pixels to the visible reference color statistics."""
    reference_rgba = _require_rgba(reference_rgba)
    target_rgba = _require_rgba(target_rgba)
    match = float(np.clip(match, *MATCH_LIMITS))
    contrast = float(np.clip(contrast, *CONTRAST_LIMITS))
    reference_sample = sample_rgba(reference_rgba)
    target_sample = sample_rgba(target_rgba)
    reference_weights = np.clip(reference_sample[:, 3], 0.0, 1.0)
    if float(reference_weights.sum()) <= 1e-8:
        raise ValueError("The color reference contains no visible pixels")

    reference_lab = linear_rgb_to_oklab(reference_sample[:, :3])
    target_sample_lab = linear_rgb_to_oklab(target_sample[:, :3])
    target_lab = linear_rgb_to_oklab(target_rgba[..., :3])
    foundation = ndimage.gaussian_filter(
        target_lab,
        sigma=(_ADJUSTMENT_SIGMA, _ADJUSTMENT_SIGMA, 0.0),
        mode="nearest",
    )

    mapped_luminance = _map_luminance(
        foundation[..., 0],
        target_sample_lab[:, 0],
        reference_lab[:, 0],
        reference_weights,
    )
    luminance_delta = _LUMINANCE_INFLUENCE * (
        mapped_luminance - foundation[..., 0]
    )
    matched_foundation = foundation[..., 0] + match * luminance_delta
    source_pivot = _weighted_quantiles(target_sample_lab[:, 0], (0.5,))[0]
    reference_pivot = _weighted_quantiles(
        reference_lab[:, 0],
        (0.5,),
        reference_weights,
    )[0]
    pivot = source_pivot + match * _LUMINANCE_INFLUENCE * (
        reference_pivot - source_pivot
    )
    target_lab[..., 0] += match * luminance_delta
    target_lab[..., 0] += contrast * (matched_foundation - pivot)

    source_mean, reference_mean, chroma_matrix = _chroma_transform(
        target_sample_lab[:, 1:],
        reference_lab[:, 1:],
        reference_weights,
    )
    foundation_chroma = foundation[..., 1:]
    mapped_chroma = (foundation_chroma.reshape((-1, 2)) - source_mean)
    mapped_chroma = mapped_chroma @ chroma_matrix + reference_mean
    mapped_chroma = mapped_chroma.reshape(foundation_chroma.shape)
    chroma = np.linalg.norm(foundation_chroma, axis=2)
    chroma_weight = 0.3 + 0.7 * np.clip((chroma - 0.006) / 0.04, 0.0, 1.0)
    target_lab[..., 1:] += (
        match
        * _CHROMA_INFLUENCE
        * chroma_weight[..., None]
        * (mapped_chroma - foundation_chroma)
    )

    if target_float:
        result_rgb = oklab_to_linear_rgb(target_lab)
    elif preview:
        result_rgb = np.clip(oklab_to_linear_rgb(target_lab), 0.0, 1.0)
    else:
        target_lab = _compress_byte_gamut(target_lab)
        result_rgb = np.clip(oklab_to_linear_rgb(target_lab), 0.0, 1.0)
        result_rgb = np.clip(result_rgb + _dither(result_rgb.shape[:2]), 0.0, 1.0)

    result = np.empty_like(target_rgba, dtype=np.float32)
    result[..., :3] = np.nan_to_num(result_rgb, nan=0.0, posinf=1.0, neginf=0.0)
    result[..., 3] = target_rgba[..., 3]
    return result


def _require_rgba(rgba):
    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[2] != 4 or min(rgba.shape[:2]) <= 0:
        raise ValueError("Color matching requires a non-empty RGBA image")
    if not np.isfinite(rgba).all():
        raise ValueError("Color matching requires finite RGBA pixels")
    return rgba


def _weighted_quantiles(values, quantiles, weights=None):
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    weights = (
        np.ones(values.shape, dtype=np.float64)
        if weights is None
        else np.asarray(weights, dtype=np.float64).reshape(-1)
    )
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0.0)
    if not np.any(valid):
        raise ValueError("Color matching requires weighted color samples")
    values = values[valid]
    weights = weights[valid]
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights) - 0.5 * weights
    cumulative /= weights.sum()
    return np.interp(quantiles, cumulative, values, left=values[0], right=values[-1])


def _map_luminance(values, source_values, reference_values, reference_weights):
    source = _weighted_quantiles(source_values, _QUANTILES)
    reference = _weighted_quantiles(
        reference_values,
        _QUANTILES,
        reference_weights,
    )
    keep = np.concatenate(([True], np.diff(source) > 1e-6))
    source = source[keep]
    reference = reference[keep]
    if len(source) == 1:
        return np.asarray(values, dtype=np.float32) + np.float32(reference[0] - source[0])
    curve = PchipInterpolator(source, reference, extrapolate=False)
    values = np.asarray(values, dtype=np.float32)
    mapped = curve(np.clip(values, source[0], source[-1])).astype(np.float32)
    mapped = np.where(values < source[0], values + reference[0] - source[0], mapped)
    return np.where(values > source[-1], values + reference[-1] - source[-1], mapped)


def _weighted_mean_covariance(values, weights=None):
    values = np.asarray(values, dtype=np.float64)
    weights = (
        np.ones(len(values), dtype=np.float64)
        if weights is None
        else np.asarray(weights, dtype=np.float64)
    )
    valid = np.isfinite(values).all(axis=1) & np.isfinite(weights) & (weights > 0.0)
    values = values[valid]
    weights = weights[valid]
    if not len(values):
        raise ValueError("Color matching requires color samples")
    total = weights.sum()
    mean = np.sum(values * weights[:, None], axis=0) / total
    centered = values - mean
    covariance = (centered * weights[:, None]).T @ centered / total
    covariance += np.eye(values.shape[1]) * _COVARIANCE_REGULARIZATION
    return mean, covariance


def _chroma_transform(source, reference, reference_weights):
    source_mean, source_covariance = _weighted_mean_covariance(source)
    reference_mean, reference_covariance = _weighted_mean_covariance(
        reference,
        reference_weights,
    )
    source_values, source_vectors = np.linalg.eigh(source_covariance)
    reference_values, reference_vectors = np.linalg.eigh(reference_covariance)
    whitening = source_vectors @ np.diag(1.0 / np.sqrt(source_values)) @ source_vectors.T
    coloring = reference_vectors @ np.diag(np.sqrt(reference_values)) @ reference_vectors.T
    matrix = whitening @ coloring
    left, scales, right = np.linalg.svd(matrix)
    scales = np.clip(scales, *_CHROMA_SCALE_LIMITS)
    matrix = left @ np.diag(scales) @ right
    return (
        source_mean.astype(np.float32),
        reference_mean.astype(np.float32),
        matrix.astype(np.float32),
    )


def _compress_byte_gamut(lab):
    lab = np.asarray(lab, dtype=np.float32).copy()
    lab[..., 0] = np.clip(lab[..., 0], 0.0, 1.0)
    flat = lab.reshape((-1, 3))
    rgb = oklab_to_linear_rgb(flat)
    indices = np.flatnonzero(np.any((rgb < 0.0) | (rgb > 1.0), axis=1))
    if not len(indices):
        return lab
    selected = flat[indices].copy()
    low = np.zeros(len(indices), dtype=np.float32)
    high = np.ones(len(indices), dtype=np.float32)
    for _iteration in range(7):
        middle = (low + high) * 0.5
        candidate = selected.copy()
        candidate[:, 1:] *= middle[:, None]
        candidate_rgb = oklab_to_linear_rgb(candidate)
        valid = np.all((candidate_rgb >= 0.0) & (candidate_rgb <= 1.0), axis=1)
        low = np.where(valid, middle, low)
        high = np.where(valid, high, middle)
    flat[indices, 1:] *= (low * 0.985)[:, None]
    return lab


def _dither(image_size):
    height, width = image_size
    pattern = np.tile(
        _BAYER_8,
        ((height + 7) // 8, (width + 7) // 8),
    )[:height, :width]
    noise = ((pattern + 0.5) / 64.0 - 0.5) * (0.55 / 255.0)
    return noise[..., None]
