"""Spherical projection and periodic radial-distance fusion."""

import numpy as np
from scipy.ndimage import map_coordinates
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import spsolve


def panorama_directions(width, height):
    u, v = np.meshgrid((np.arange(width) + 0.5) / width,
                       (np.arange(height) + 0.5) / height)
    return uv_directions(u, v)


def uv_directions(u, v):
    theta, phi = 2 * np.pi * u, np.pi * v
    return np.stack((np.sin(phi) * np.cos(theta),
                     np.sin(phi) * np.sin(theta), np.cos(phi)), axis=-1)


def camera_bases():
    ratio = (1 + np.sqrt(5)) / 2
    vertices = []
    for a in (-1, 1):
        for b in (-ratio, ratio):
            vertices.extend(((0, a, b), (a, b, 0), (b, 0, a)))
    bases = []
    for forward in np.asarray(vertices):
        forward = forward / np.linalg.norm(forward)
        right = np.cross(forward, (0, 0, 1))
        right /= np.linalg.norm(right)
        down = np.cross(forward, right)
        bases.append(np.stack((right, down, forward)))
    return bases


def view_rays(size):
    x, y = np.meshgrid(2 * (np.arange(size) + 0.5) / size - 1,
                       2 * (np.arange(size) + 0.5) / size - 1)
    return np.stack((x, y, np.ones_like(x)), axis=-1)


def sample_panorama(image, directions, *, order=1):
    directions = directions / np.linalg.norm(directions, axis=-1, keepdims=True)
    u = np.arctan2(directions[..., 1], directions[..., 0]) / (2 * np.pi) % 1
    v = np.arccos(np.clip(directions[..., 2], -1, 1)) / np.pi
    height, width = image.shape[:2]
    padded = np.concatenate((image[:, -1:], image, image[:, :1]), axis=1)
    coords = (np.clip(v * height - 0.5, 0, height - 1), u * width + 0.5)
    if image.ndim == 2:
        return map_coordinates(padded, coords, order=order, mode="nearest")
    return np.stack([map_coordinates(padded[..., c], coords, order=order,
                                    mode="nearest") for c in range(image.shape[2])], -1)


def warp_distances(distances, masks, bases, width, height, *, directions=None):
    if directions is None:
        directions = panorama_directions(width, height)
    logs, validities = [], []
    for distance, mask, basis in zip(distances, masks, bases):
        rays = directions @ basis.T
        projected = rays[..., :2] / np.maximum(rays[..., 2:], 1e-8)
        valid = (rays[..., 2] > 0) & (np.abs(projected) < 0.98).all(axis=-1)
        size = distance.shape[0]
        coords = ((projected[..., 1] + 1) * size / 2 - 0.5,
                  (projected[..., 0] + 1) * size / 2 - 0.5)
        valid &= map_coordinates(mask.astype(float), coords, order=0, mode="nearest") > 0.5
        logs.append(map_coordinates(np.log(np.maximum(distance, 1e-6)), coords,
                                    order=1, mode="nearest"))
        validities.append(valid)
    return np.asarray(logs), np.asarray(validities)


def merge_distances(distances, masks, bases, width, height, *, cancel_check=None):
    """Fuse log-distance derivatives with a cyclic longitude and a scale anchor.

    Algorithm reference: microsoft/MoGe, moge/utils/panorama.py.
    This independent implementation solves normal equations on a bounded panorama grid.
    """
    if cancel_check is not None:
        cancel_check()
    if width > 512:
        return _refine_distances(distances, masks, bases, width, height, cancel_check)
    logs, valid = warp_distances(distances, masks, bases, width, height)
    view_count = len(logs)
    count = width * height
    index = np.arange(count).reshape(height, width)
    start = np.concatenate((index.ravel(), index[:-1].ravel()))
    end = np.concatenate((np.roll(index, -1, axis=1).ravel(), index[1:].ravel()))
    rows = np.arange(len(start))
    gradient = coo_matrix((np.concatenate((-np.ones(len(start)), np.ones(len(start)))),
                          (np.tile(rows, 2), np.concatenate((start, end)))),
                         shape=(len(start), count)).tocsr()
    laplacian = -(gradient.T @ gradient).tocsr()
    edge_valid = valid.reshape(view_count, -1)[:, start] & valid.reshape(view_count, -1)[:, end]
    grad_samples = logs.reshape(view_count, -1)[:, end] - logs.reshape(view_count, -1)[:, start]
    grad_target = np.sum(grad_samples * edge_valid, axis=0) / np.maximum(edge_valid.sum(0), 1)
    lap_valid = valid.copy()
    lap_valid &= np.roll(valid, 1, axis=2) & np.roll(valid, -1, axis=2)
    lap_valid[:, 1:] &= valid[:, :-1]
    lap_valid[:, :-1] &= valid[:, 1:]
    lap_valid = lap_valid.reshape(view_count, -1)
    lap_samples = np.asarray((laplacian @ logs.reshape(view_count, -1).T).T)
    lap_target = np.sum(lap_samples * lap_valid, axis=0) / np.maximum(lap_valid.sum(0), 1)
    g = gradient[edge_valid.any(0)]
    l = laplacian[lap_valid.any(0)]
    coverage = valid.any(0)
    if not coverage.any():
        raise ValueError("No valid panorama predictions")
    baseline = np.sum(logs * valid, axis=0) / np.maximum(valid.sum(0), 1)
    matrix = g.T @ g + l.T @ l + diags(np.full(count, 1e-7))
    target = g.T @ grad_target[edge_valid.any(0)] + l.T @ lap_target[lap_valid.any(0)]
    if cancel_check is not None:
        cancel_check()
    solution = spsolve(matrix.tocsc(), target + 1e-7 * baseline.ravel()).reshape(height, width)
    if cancel_check is not None:
        cancel_check()
    solution += np.median(baseline[coverage] - solution[coverage])
    return np.exp(solution).astype(np.float32), coverage


def _refine_distances(distances, masks, bases, width, height, cancel_check):
    """Apply coarse periodic alignment to view detail in bounded output tiles."""
    coarse_width, coarse_height = 512, 256
    coarse, _ = merge_distances(distances, masks, bases, coarse_width, coarse_height,
                                       cancel_check=cancel_check)
    logs, valid = warp_distances(distances, masks, bases, coarse_width, coarse_height)
    corrections = np.log(coarse)[None] - logs
    result = np.empty((height, width), np.float32)
    mask = np.empty((height, width), bool)
    tile_height = max(1, 65536 // width)
    for start in range(0, height, tile_height):
        if cancel_check is not None:
            cancel_check()
        stop = min(start + tile_height, height)
        u, v = np.meshgrid((np.arange(width) + 0.5) / width,
                           (np.arange(start, stop) + 0.5) / height)
        directions = uv_directions(u, v)
        detail, visible = warp_distances(distances, masks, bases, width, height,
                                         directions=directions)
        total = np.zeros(u.shape)
        weights = np.zeros(u.shape)
        for index, basis in enumerate(bases):
            support = sample_panorama(valid[index].astype(float), directions)
            correction = sample_panorama(corrections[index] * valid[index], directions)
            correction /= np.maximum(support, 1e-8)
            forward = directions @ basis[2]
            weight = visible[index] * np.maximum(forward, 0) ** 4 * (support > 1e-8)
            total += (detail[index] + correction) * weight
            weights += weight
        fallback = sample_panorama(np.log(coarse), directions)
        np.divide(total, weights, out=fallback, where=weights > 0)
        result[start:stop] = np.exp(fallback)
        mask[start:stop] = visible.any(axis=0)
    return result, mask

