"""Deterministic perceptual color matching for RGBA images."""

from typing import NamedTuple

import numpy as np
from scipy import ndimage
from scipy.interpolate import PchipInterpolator
from scipy.optimize import linprog


_ANALYSIS_SAMPLES = 65_536
_QUANTILES = np.asarray((0.0, 0.02, 0.08, 0.2, 0.5, 0.8, 0.92, 0.98, 1.0))
_CHROMA_SCALE_LIMITS = (0.6, 1.65)
_COVARIANCE_REGULARIZATION = 4e-4
_ADJUSTMENT_SIGMA = 2.0
_SIGNATURE_MAX_SIZE = 256
_SIGNATURE_CANDIDATES = 24
_SIGNATURE_MIN_ANCHORS = 8
_SIGNATURE_MAX_ANCHORS = 16
_SIGNATURE_ERROR_LIMIT = 0.021
_SIGNATURE_BLEND_SIGMA = 0.085
_PALETTE_MAX_COLORS = 7
COLOR_LIMITS = (0.0, 1.0)
LIGHTNESS_LIMITS = (0.0, 1.0)
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


class ColorSignature(NamedTuple):
    """Perceptual representative colors and their normalized importance."""

    colors: np.ndarray
    weights: np.ndarray


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


def extract_reference_palette(reference_rgba):
    """Return dynamic display colors and weights from the matching signature."""
    signature = extract_color_signature(reference_rgba, alpha_weighted=True)
    palette = _collapse_signature_palette(signature)
    colors = np.clip(oklab_to_linear_rgb(palette.colors), 0.0, 1.0)
    return colors.astype(np.float32), palette.weights


def match_color_reference(
    reference_rgba,
    target_rgba,
    *,
    target_float=False,
    color=1.0,
    lightness=1.0,
    preview=False,
    reference_signature=None,
    target_signature=None,
):
    """Match all target RGB pixels to the visible reference color statistics."""
    reference_rgba = _require_rgba(reference_rgba)
    target_rgba = _require_rgba(target_rgba)
    color = float(np.clip(color, *COLOR_LIMITS))
    lightness = float(np.clip(lightness, *LIGHTNESS_LIMITS))
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
    luminance_delta = mapped_luminance - foundation[..., 0]
    target_lab[..., 0] += lightness * luminance_delta

    reference_signature = reference_signature or extract_color_signature(
        reference_rgba, alpha_weighted=True
    )
    target_signature = target_signature or extract_color_signature(
        target_rgba, alpha_weighted=False
    )
    mapped_anchors = _transport_signature(target_signature, reference_signature)
    anchor_delta = mapped_anchors - target_signature.colors[:, 1:]
    foundation_chroma = foundation[..., 1:]
    chroma_delta = _blend_anchor_delta(
        foundation,
        target_signature.colors,
        anchor_delta,
    )
    target_lab[..., 1:] += color * chroma_delta

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


def extract_color_signature(rgba, *, alpha_weighted):
    """Extract an adaptive spatial color signature in OKLab."""
    rgba = _require_rgba(rgba)
    if alpha_weighted:
        premultiplied = rgba.copy()
        premultiplied[..., :3] *= premultiplied[..., 3:4]
        proxy = resize_rgba_proxy(
            premultiplied,
            max_size=_SIGNATURE_MAX_SIZE,
        )
        visible = proxy[..., 3] > 1e-6
        proxy[visible, :3] /= proxy[visible, 3:4]
    else:
        proxy = resize_rgba_proxy(rgba, max_size=_SIGNATURE_MAX_SIZE)
    lab = linear_rgb_to_oklab(proxy[..., :3])
    pixel_weights = (
        np.clip(proxy[..., 3], 0.0, 1.0)
        if alpha_weighted
        else np.ones(proxy.shape[:2], dtype=np.float32)
    )
    valid = pixel_weights > 1e-6
    if not np.any(valid):
        raise ValueError("The color reference contains no visible pixels")

    values = lab[valid]
    weights = pixel_weights[valid].astype(np.float64)
    candidate_limit = min(_SIGNATURE_CANDIDATES, len(values))
    weighted_mean = np.average(values, axis=0, weights=weights)
    first = int(np.argmin(np.sum((values - weighted_mean) ** 2, axis=1)))
    centers = [values[first]]
    nearest = np.full(len(values), np.inf, dtype=np.float64)
    for _index in range(1, candidate_limit):
        distance = np.sum((values - centers[-1]) ** 2, axis=1)
        nearest = np.minimum(nearest, distance)
        if float(nearest.max()) <= 1e-10:
            break
        centers.append(values[np.argmax(nearest * np.sqrt(weights))])
    centers = np.asarray(centers, dtype=np.float64)

    for _iteration in range(16):
        distance = np.sum((values[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(distance, axis=1)
        previous = centers.copy()
        for index in range(len(centers)):
            selected = labels == index
            if np.any(selected):
                centers[index] = np.average(
                    values[selected],
                    axis=0,
                    weights=weights[selected],
                )
        if np.max(np.abs(centers - previous)) <= 1e-6:
            break

    distance = np.sum((values[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    labels = np.argmin(distance, axis=1)
    label_map = np.full(proxy.shape[:2], -1, dtype=np.int16)
    label_map[valid] = labels
    candidate_weights = np.bincount(
        labels,
        weights=weights,
        minlength=len(centers),
    ).astype(np.float64)
    area = candidate_weights / candidate_weights.sum()
    center_distance = np.sqrt(
        np.sum((centers[:, None, :] - centers[None, :, :]) ** 2, axis=2)
    )
    distinctiveness = center_distance @ area
    boundary = _candidate_boundary_contrast(
        label_map,
        pixel_weights,
        center_distance,
    )
    coherence = _candidate_coherence(
        label_map,
        pixel_weights,
        candidate_weights,
    )
    chroma = np.linalg.norm(centers[:, 1:], axis=1)
    saliency = (
        area**0.35
        * (0.35 + 0.65 * _normalize_feature(distinctiveness))
        * (0.35 + 0.65 * _normalize_feature(boundary))
        * (0.45 + 0.55 * np.sqrt(coherence))
        * (0.55 + 0.45 * np.clip(chroma / 0.12, 0.0, 1.0))
    )
    if float(saliency.sum()) <= 1e-12:
        saliency = area.copy()

    selected = _select_signature_anchors(
        centers,
        area,
        boundary,
        coherence,
        saliency,
    )
    group_distance = np.sum(
        (centers[:, None, 1:] - centers[selected][None, :, 1:]) ** 2,
        axis=2,
    )
    groups = np.argmin(group_distance, axis=1)
    signature_weights = np.asarray(
        [saliency[groups == index].sum() for index in range(len(selected))],
        dtype=np.float64,
    )
    signature_weights /= signature_weights.sum()

    representatives = []
    for candidate in selected:
        region = values[labels == candidate]
        region_chroma = np.linalg.norm(region[:, 1:], axis=1)
        vivid = region[region_chroma >= np.quantile(region_chroma, 0.65)]
        vivid_distance = np.sum((vivid - centers[candidate]) ** 2, axis=1)
        representatives.append(vivid[np.argmin(vivid_distance)])
    return ColorSignature(
        np.asarray(representatives, dtype=np.float32),
        signature_weights.astype(np.float32),
    )


def _candidate_boundary_contrast(label_map, pixel_weights, center_distance):
    count = len(center_distance)
    contrast_sum = np.zeros(count, dtype=np.float64)
    boundary_weight = np.zeros(count, dtype=np.float64)
    pairs = (
        (label_map[:, :-1], label_map[:, 1:], pixel_weights[:, :-1], pixel_weights[:, 1:]),
        (label_map[:-1, :], label_map[1:, :], pixel_weights[:-1, :], pixel_weights[1:, :]),
    )
    for first, second, first_weight, second_weight in pairs:
        changed = (first >= 0) & (second >= 0) & (first != second)
        left = first[changed]
        right = second[changed]
        weights = np.minimum(first_weight[changed], second_weight[changed])
        contrast = center_distance[left, right] * weights
        np.add.at(contrast_sum, left, contrast)
        np.add.at(contrast_sum, right, contrast)
        np.add.at(boundary_weight, left, weights)
        np.add.at(boundary_weight, right, weights)
    return contrast_sum / np.maximum(boundary_weight, 1e-8)


def _candidate_coherence(label_map, pixel_weights, candidate_weights):
    coherence = np.zeros(len(candidate_weights), dtype=np.float64)
    structure = np.ones((3, 3), dtype=np.uint8)
    for index in range(len(candidate_weights)):
        connected, component_count = ndimage.label(
            label_map == index,
            structure=structure,
        )
        if component_count:
            component_weights = np.bincount(
                connected.reshape(-1),
                weights=pixel_weights.reshape(-1),
            )[1:]
            coherence[index] = component_weights.max() / candidate_weights[index]
    return np.clip(coherence, 0.0, 1.0)


def _normalize_feature(values):
    values = np.asarray(values, dtype=np.float64)
    low, high = np.percentile(values, (10.0, 90.0))
    if high <= low + 1e-8:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def _select_signature_anchors(centers, area, boundary, coherence, saliency):
    maximum = min(_SIGNATURE_MAX_ANCHORS, len(centers))
    minimum = min(_SIGNATURE_MIN_ANCHORS, maximum)
    order = np.argsort(-saliency)
    selected = []
    for index in order:
        if selected:
            chosen = centers[np.asarray(selected)]
            color_distance = np.sqrt(np.sum((centers[index] - chosen) ** 2, axis=1))
            chroma_distance = np.sqrt(
                np.sum((centers[index, 1:] - chosen[:, 1:]) ** 2, axis=1)
            )
            duplicate = (chroma_distance < 0.035) & (color_distance < 0.13)
            region_exception = (
                coherence[index] > 0.55
                and boundary[index] > 0.105
                and area[index] < 0.08
            )
            if np.any(duplicate) and not region_exception:
                continue
        selected.append(int(index))
        if len(selected) == maximum:
            break
    if len(selected) < minimum:
        selected.extend(
            int(index) for index in order if index not in selected
        )
    selected = np.asarray(selected[:maximum], dtype=np.intp)

    for count in range(minimum, len(selected) + 1):
        distance = np.sqrt(
            np.min(
                np.sum(
                    (
                        centers[:, None, 1:]
                        - centers[selected[:count]][None, :, 1:]
                    )
                    ** 2,
                    axis=2,
                ),
                axis=1,
            )
        )
        error = np.sqrt(np.sum(saliency * distance**2) / saliency.sum())
        if error <= _SIGNATURE_ERROR_LIMIT:
            return selected[:count]
    return selected


def _transport_signature(source, reference):
    source_count = len(source.colors)
    reference_count = len(reference.colors)
    source_weights = np.asarray(source.weights, dtype=np.float64)
    reference_weights = np.asarray(reference.weights, dtype=np.float64)
    source_weights /= source_weights.sum()
    reference_weights /= reference_weights.sum()
    source_mean, reference_mean, matrix = _chroma_transform(
        source.colors[:, 1:],
        reference.colors[:, 1:],
        reference_weights,
        source_weights,
    )
    aligned = (source.colors[:, 1:] - source_mean) @ matrix + reference_mean
    cost = np.sum(
        (aligned[:, None, :] - reference.colors[None, :, 1:]) ** 2,
        axis=2,
    )
    source_rank = np.argsort(np.argsort(source.colors[:, 0])) / max(source_count - 1, 1)
    reference_rank = np.argsort(np.argsort(reference.colors[:, 0])) / max(
        reference_count - 1,
        1,
    )
    cost += 0.15 * (source_rank[:, None] - reference_rank[None, :]) ** 2

    equalities = []
    for source_index in range(source_count):
        row = np.zeros((source_count, reference_count), dtype=np.float64)
        row[source_index, :] = 1.0
        equalities.append(row.reshape(-1))
    for reference_index in range(reference_count):
        row = np.zeros((source_count, reference_count), dtype=np.float64)
        row[:, reference_index] = 1.0
        equalities.append(row.reshape(-1))
    result = linprog(
        cost.reshape(-1),
        A_eq=np.asarray(equalities),
        b_eq=np.concatenate((source_weights, reference_weights)),
        bounds=(0.0, None),
        method="highs",
    )
    if not result.success:
        return aligned.astype(np.float32)
    flow = result.x.reshape((source_count, reference_count))
    mapped = flow @ reference.colors[:, 1:]
    mapped /= np.maximum(source_weights[:, None], 1e-8)
    return mapped.astype(np.float32)


def _blend_anchor_delta(lab, anchors, delta):
    flat = np.asarray(lab, dtype=np.float32).reshape((-1, 3))
    output = np.empty((len(flat), 2), dtype=np.float32)
    for start in range(0, len(flat), 131_072):
        chunk = flat[start : start + 131_072]
        distance = np.sum((chunk[:, None, :] - anchors[None, :, :]) ** 2, axis=2)
        membership = np.exp(
            -distance / (2.0 * _SIGNATURE_BLEND_SIGMA**2),
            dtype=np.float32,
        )
        membership /= np.maximum(membership.sum(axis=1, keepdims=True), 1e-8)
        output[start : start + len(chunk)] = membership @ delta
    return output.reshape((*lab.shape[:2], 2))


def _collapse_signature_palette(signature):
    groups = [
        [signature.colors[index].copy(), float(signature.weights[index])]
        for index in np.argsort(-signature.weights)
    ]
    minimum = min(3, len(groups))

    def more_chromatic(first, second):
        return (
            first
            if np.linalg.norm(groups[first][0][1:])
            >= np.linalg.norm(groups[second][0][1:])
            else second
        )

    def perceptual_distance(first, second):
        chroma = np.linalg.norm(first[0][1:] - second[0][1:])
        lightness = abs(float(first[0][0] - second[0][0]))
        return chroma + 0.16 * lightness

    changed = True
    while changed and len(groups) > minimum:
        changed = False
        for first in range(len(groups)):
            for second in range(first + 1, len(groups)):
                chroma = np.linalg.norm(groups[first][0][1:] - groups[second][0][1:])
                lightness = abs(float(groups[first][0][0] - groups[second][0][0]))
                if chroma < 0.05 and lightness < 0.22:
                    keeper = more_chromatic(first, second)
                    removed = second if keeper == first else first
                    groups[keeper][1] += groups[removed][1]
                    del groups[removed]
                    changed = True
                    break
            if changed:
                break

    while len(groups) > minimum:
        smallest = min(range(len(groups)), key=lambda index: groups[index][1])
        if groups[smallest][1] >= 0.04:
            break
        nearest = min(
            (index for index in range(len(groups)) if index != smallest),
            key=lambda index: perceptual_distance(groups[smallest], groups[index]),
        )
        keeper = more_chromatic(smallest, nearest)
        removed = nearest if keeper == smallest else smallest
        groups[keeper][1] += groups[removed][1]
        del groups[removed]

    while len(groups) > _PALETTE_MAX_COLORS:
        _distance, first, second = min(
            (
                (perceptual_distance(groups[first], groups[second]), first, second)
                for first in range(len(groups))
                for second in range(first + 1, len(groups))
            ),
            key=lambda item: item[0],
        )
        keeper = more_chromatic(first, second)
        removed = second if keeper == first else first
        groups[keeper][1] += groups[removed][1]
        del groups[removed]

    groups.sort(key=lambda group: -group[1])
    weights = np.asarray([group[1] for group in groups], dtype=np.float32)
    weights /= weights.sum()
    return ColorSignature(
        np.asarray([group[0] for group in groups], dtype=np.float32),
        weights,
    )


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


def _chroma_transform(source, reference, reference_weights, source_weights=None):
    source_mean, source_covariance = _weighted_mean_covariance(
        source,
        source_weights,
    )
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
