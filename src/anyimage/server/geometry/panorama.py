"""Spherical projection and periodic radial-distance fusion."""

import numpy as np


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


def panorama_sample_coordinates(directions, image_shape):
    """Map view directions to row and column coordinates in a seam-padded panorama."""
    directions = directions / np.linalg.norm(directions, axis=-1, keepdims=True)
    u = np.arctan2(directions[..., 1], directions[..., 0]) / (2 * np.pi) % 1
    v = np.arccos(np.clip(directions[..., 2], -1, 1)) / np.pi
    height, width = image_shape
    return np.clip(v * height - 0.5, 0, height - 1), u * width + 0.5


def pad_panorama_seam(image):
    return np.concatenate((image[:, -1:], image, image[:, :1]), axis=1)


def sample_panorama(padded, coords, *, order=1):
    from scipy.ndimage import map_coordinates

    if padded.ndim == 2:
        return map_coordinates(padded, coords, order=order, mode="nearest")

    channels = [
        map_coordinates(padded[..., channel], coords, order=order, mode="nearest")
        for channel in range(padded.shape[2])
    ]
    return np.stack(channels, axis=-1)


def merge_normals(normals, masks, bases, width, height, *, coverage=None, cancel_check=None):
    """Rotate camera normals and blend them in panorama object coordinates."""
    from scipy.ndimage import map_coordinates

    fields = []
    for normal, mask, basis in zip(normals, masks, bases):
        if not mask.any():
            continue
        normal = np.asarray(normal, dtype=np.float32)
        length = np.sqrt(np.einsum("...i,...i->...", normal, normal))
        valid = mask & np.isfinite(length) & (length > 1e-8)
        unit = np.zeros_like(normal)
        np.divide(normal, length[..., None], out=unit, where=valid[..., None])
        basis = np.asarray(basis, dtype=np.float32)
        fields.append((unit @ basis, basis))
    result = np.empty((height, width, 3), np.float32)
    tile_height = max(1, 65536 // width)
    columns = (np.arange(width, dtype=np.float32) + .5) / width
    for start in range(0, height, tile_height):
        if cancel_check is not None:
            cancel_check()
        stop = min(start + tile_height, height)
        u, v = np.meshgrid(columns, (np.arange(start, stop, dtype=np.float32) + .5) / height)
        directions = uv_directions(u, v)
        active = np.ones(directions.shape[:2], dtype=bool) if coverage is None else coverage[start:stop]
        visible = directions[active]
        total = np.zeros_like(visible)
        for field, basis in fields:
            rays = visible @ basis.T
            edge = np.maximum(abs(rays[:, 0]), abs(rays[:, 1]))
            inside = np.flatnonzero(edge < rays[:, 2])
            if not inside.size:
                continue
            forward = rays[inside, 2]
            projected = rays[inside, :2] / forward[:, None]
            coords = ((projected[:, 1] + 1) * field.shape[0] / 2 - .5,
                      (projected[:, 0] + 1) * field.shape[1] / 2 - .5)
            weight = forward ** 4 * np.clip((1 - edge[inside] / forward) / .2, 0, 1)
            # Invalid normals are already zero before interpolation.
            for channel in range(3):
                sampled = map_coordinates(field[..., channel], coords, order=1, mode="nearest")
                total[inside, channel] += sampled * weight
        length = np.sqrt(np.einsum("ij,ij->i", total, total))[:, None]
        merged = -visible
        np.divide(total, length, out=merged, where=length > 1e-8)
        directions *= -1
        directions[active] = merged
        # Mesh UV longitude is pi - theta; its vertical axis remains +Z.
        directions[..., 0] *= -1
        result[start:stop] = directions
    return result


def _sample_view_depth(log_distance, mask, basis, directions):
    """Sample one view at visible panorama pixels and return their forward cosines."""
    from scipy.ndimage import map_coordinates

    rays = directions @ basis.T
    edge = np.maximum(abs(rays[..., 0]), abs(rays[..., 1]))
    rows, cols = np.nonzero(edge < 0.98 * rays[..., 2])
    rays = rays[rows, cols]
    forward = rays[:, 2]
    projected = rays[:, :2] / forward[:, None]
    size = log_distance.shape[0]
    coords = ((projected[:, 1] + 1) * size / 2 - .5,
              (projected[:, 0] + 1) * size / 2 - .5)
    visible = map_coordinates(mask, coords, order=0, mode="nearest") > .5
    coords = tuple(axis[visible] for axis in coords)
    depth = map_coordinates(log_distance, coords, order=1, mode="nearest")
    return (rows[visible], cols[visible]), depth, forward[visible]


def _solve_log_distances(logs, valid, cancel_check):
    """Fuse log-distance derivatives with a cyclic longitude and a scale anchor.

    Algorithm reference: microsoft/MoGe, moge/utils/panorama.py.
    This independent implementation solves normal equations on a bounded panorama grid.
    """
    from scipy.sparse import coo_matrix, diags
    from scipy.sparse.linalg import splu

    view_count, height, width = logs.shape
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
    # The gradient and Laplacian Gram matrices plus the positive diagonal are SPD.
    factor = splu(matrix.tocsc(), permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.0,
                  options={"SymmetricMode": True})
    solution = factor.solve(target + 1e-7 * baseline.ravel()).reshape(height, width)
    if cancel_check is not None:
        cancel_check()
    solution += np.median(baseline[coverage] - solution[coverage])
    return solution, coverage


def merge_distances(distances, masks, bases, width, height, *, cancel_check=None):
    """Align the views on a bounded grid, then restore full-resolution detail."""
    from scipy.ndimage import map_coordinates

    if cancel_check is not None:
        cancel_check()
    coarse_width, coarse_height = (512, 256) if width > 512 else (width, height)
    log_distances = [np.log(np.maximum(distance, 1e-6)) for distance in distances]
    directions = panorama_directions(coarse_width, coarse_height)
    logs = np.zeros((len(bases), coarse_height, coarse_width), dtype=np.result_type(*log_distances))
    valid = np.zeros(logs.shape, dtype=bool)
    for i, (view, mask, basis) in enumerate(zip(log_distances, masks, bases)):
        pixels, samples, _ = _sample_view_depth(view, mask, basis, directions)
        logs[i][pixels] = samples
        valid[i][pixels] = True
    coarse_log, coverage = _solve_log_distances(logs, valid, cancel_check)
    if width == coarse_width:
        return np.exp(coarse_log).astype(np.float32), coverage

    corrections = (coarse_log[None] - logs) * valid
    # Pad longitude once; tile UVs already provide the exact coarse sampling coordinates.
    support_maps = np.pad(valid.astype(float), ((0, 0), (0, 0), (1, 1)), mode="wrap")
    correction_maps = np.pad(corrections, ((0, 0), (0, 0), (1, 1)), mode="wrap")
    fallback_map = np.pad(coarse_log, ((0, 0), (1, 1)), mode="wrap")
    result = np.empty((height, width), np.float32)
    mask = np.zeros((height, width), bool)
    tile_height = max(1, 65536 // width)
    for start in range(0, height, tile_height):
        if cancel_check is not None:
            cancel_check()
        stop = min(start + tile_height, height)
        u, v = np.meshgrid((np.arange(width) + 0.5) / width,
                           (np.arange(start, stop) + 0.5) / height)
        directions = uv_directions(u, v)
        total = np.zeros(u.shape)
        weights = np.zeros(u.shape)
        coords = (np.clip(v * coarse_height - .5, 0, coarse_height - 1), u * coarse_width + .5)
        for index, (view, view_mask, basis) in enumerate(zip(log_distances, masks, bases)):
            pixels, detail, forward = _sample_view_depth(view, view_mask, basis, directions)
            view_coords = tuple(coordinate[pixels] for coordinate in coords)
            support = map_coordinates(support_maps[index], view_coords, order=1, mode="nearest")
            correction = map_coordinates(correction_maps[index], view_coords, order=1, mode="nearest")
            correction /= np.maximum(support, 1e-8)
            weight = forward ** 4 * (support > 1e-8)
            total[pixels] += (detail + correction) * weight
            weights[pixels] += weight
            mask[start:stop][pixels] = True
        fallback = map_coordinates(fallback_map, coords, order=1, mode="nearest")
        np.divide(total, weights, out=fallback, where=weights > 0)
        result[start:stop] = np.exp(fallback)
    return result, mask

