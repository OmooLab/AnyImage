"""Recover continuous surface detail from panorama depth and normal predictions."""

import numpy as np
from scipy.fft import irfft, rfft, rfftfreq
from scipy.ndimage import distance_transform_edt, gaussian_filter1d, map_coordinates
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import cg


RELIEF_SCALE_DEGREES = 2.5


def _unit(field):
    return field / np.maximum(np.linalg.norm(field, axis=-1, keepdims=True), 1e-12)


def _dot(a, b):
    return np.sum(a * b, axis=-1)


def _derivative(field, forward, axis):
    backward = np.roll(forward, 1, axis=axis)
    plus = np.roll(field, -1, axis=axis) - field
    minus = field - np.roll(field, 1, axis=axis)
    count = forward.astype(np.float32) + backward
    return (plus * forward[..., None] + minus * backward[..., None]) / np.maximum(count[..., None], 1)


def _normals(points, rays, horizontal, vertical):
    tangent_x = _derivative(points, horizontal, 1)
    tangent_y = _derivative(points, vertical, 0)
    product = np.cross(tangent_x, tangent_y)
    area = np.linalg.norm(product, axis=-1)
    normal = product / np.maximum(area[..., None], 1e-12)
    normal[_dot(normal, rays) > 0] *= -1
    degenerate = area < 1e-12
    normal[degenerate] = -rays[degenerate]
    return normal.astype(np.float32), tangent_x, area


def _angular_kernel(width, sigma, latitude_scale):
    # A longitude sample covers less surface near the poles. Use the same
    # angular footprint around each pixel rather than a constant UV radius.
    frequency = rfftfreq(width).astype(np.float32)
    sigma_x = sigma / np.maximum(latitude_scale, .02)
    return np.exp(-2 * np.pi**2 * (sigma_x[:, None] * frequency) ** 2)


def _angular_blur(field, kernel, sigma):
    horizontal = irfft(rfft(field, axis=1) * kernel[..., None], n=field.shape[1], axis=1)
    return gaussian_filter1d(horizontal, sigma, axis=0, mode='nearest')


def _polar_geometry(raw_log_depth, rays, valid, phi, cell_degrees):
    """Remove longitude offsets and recover the limiting pointmap tangent plane."""
    adjusted = raw_log_depth.copy()
    caps = []
    for radius in (np.rad2deg(phi), 180 - np.rad2deg(phi)):
        cap = radius < 6 * cell_degrees
        ring = (radius >= cell_degrees) & (radius <= 5 * cell_degrees)
        if not cap.any() or not ring.any() or valid[ring].mean() < .95:
            continue
        points = rays[ring] * np.exp(raw_log_depth[ring])[..., None]
        weights = valid[ring]
        # Remove each meridian's constant height offset before fitting slopes.
        # This separates a real surface slope from a coordinate artifact at the pole.
        center = np.sum(points * weights[..., None], axis=0) / np.maximum(weights.sum(0)[:, None], 1)
        offsets = (points - center)[weights]
        slope = np.linalg.lstsq(offsets[:, :2], offsets[:, 2], rcond=None)[0]
        intercept = np.median(points[..., 2][weights] - points[..., :2][weights] @ slope)
        if abs(intercept) < 1e-8:
            continue
        inverse_depth = (rays[cap, :, 2] - rays[cap, :, :2] @ slope) / intercept
        if np.any(inverse_depth <= 0):
            continue
        offset = center[:, 2] - center[:, :2] @ slope - intercept
        spectrum = rfft(offset)
        spectrum[0] = 0
        spectrum[5:] = 0
        offset = irfft(spectrum, n=len(offset))
        if np.ptp(offset) < .005 * abs(intercept):
            continue
        polar_region = radius < 8 * cell_degrees
        fade = np.clip((radius[polar_region] / cell_degrees - 3) / 5, 0, 1)[:, None]
        fade = 1 - fade**3 * (10 - 15 * fade + 6 * fade**2)
        depth = np.exp(raw_log_depth[polar_region]) - fade * offset[None, :] / rays[polar_region, :, 2]
        adjusted[polar_region] = np.log(np.maximum(depth, 1e-6))
        plane_depth = (rays[..., 2] - rays[..., :2] @ slope) / intercept
        plane_depth = -np.log(np.maximum(plane_depth, 1e-8))
        caps.append((radius, cap, plane_depth))
    return adjusted, caps


def _extend_polar_field(field, radius, cap, anchor):
    """Continue a scalar field into a polar chart with matched value and slope."""
    # Put the join on an existing latitude sample. Fourier mode k is regular
    # at the origin only if it decays at least as r**k. The first two modes
    # decay faster so the fitted pointmap plane fixes height and slope there.
    boundary = np.flatnonzero(cap)[np.argmax(radius[cap])]
    step = -1 if boundary < len(radius) / 2 else 1
    outside = boundary - step
    inside = boundary + step
    t = np.tan(np.deg2rad(radius[cap])) / np.tan(np.deg2rad(radius[boundary]))
    u_out = np.tan(np.deg2rad(radius[outside])) / np.tan(np.deg2rad(radius[boundary]))
    u_in = np.tan(np.deg2rad(radius[inside])) / np.tan(np.deg2rad(radius[boundary]))
    difference = field - anchor
    value = rfft(difference[boundary])
    slope = rfft((difference[outside] - difference[inside]) / (u_out - u_in))
    degree = np.arange(len(value), dtype=np.float32)
    degree[:2] += 2
    # t**k [a + b(t²−1)] interpolates both the outer height and its derivative.
    coefficients = t[:, None] ** degree * (
        value + .5 * (slope - degree * value) * (t[:, None] ** 2 - 1))
    field[cap] = anchor[cap] + irfft(coefficients, n=field.shape[1], axis=1)


def _tangent_slopes(predicted, rays, longitude, reference, point_u, source_base):
    """Transfer slopes in UV-aligned tangent frames, without rotating final normals."""
    source_facing = _dot(source_base, rays)
    # Move along the same image longitude on the source and target tangent planes.
    source_u = longitude * source_facing[..., None] - rays * _dot(source_base, longitude)[..., None]
    source_u = _unit(source_u) * np.sign(source_facing)[..., None]
    source_v = np.cross(source_base, source_u)
    target_u = _unit(point_u - reference * _dot(reference, point_u)[..., None])
    target_v = np.cross(reference, target_u)
    local_alignment = np.maximum(_dot(predicted, source_base), 0)
    slope = -(target_u * _dot(predicted, source_u)[..., None] + target_v * _dot(predicted, source_v)[..., None])
    slope /= np.maximum(local_alignment[..., None], 1e-4)
    # Near-grazing or oppositely oriented estimates cannot describe a local bump.
    confidence = local_alignment ** 4 * np.minimum(1, (source_facing / .2) ** 2)
    return slope.astype(np.float32), confidence.astype(np.float32)


def _integrate(points, slope, confidence, valid, horizontal, vertical, area, screen_pixels, cancel_check):
    """Fit one relief height to adjacent surface slope measurements."""
    row, col = np.nonzero(valid)
    count = len(row)
    ids = np.full(valid.shape, -1, dtype=np.int32)
    ids[row, col] = np.arange(count, dtype=np.int32)
    # Length cutoff measured in local pointmap samples. The physical area in the
    # screening term cancels the area used to convert wavelength to meters.
    screen = np.float32(screen_pixels ** -2)
    diagonal = np.full(count, screen, dtype=np.float32)
    rhs = np.zeros(count, dtype=np.float32)
    width = valid.shape[1]
    flat_ids = ids.ravel()
    flat_points = points.reshape(-1, 3)
    flat_slope = slope.reshape(-1, 3)
    flat_area = area.ravel()
    flat_confidence = confidence.ravel()
    starts, ends, weights = [], [], []
    for axis, edge in ((1, horizontal), (0, vertical)):
        if cancel_check is not None:
            cancel_check()
        source = np.flatnonzero(edge)
        if axis == 1:
            neighbor = source + 1 - width * (source % width == width - 1)
        else:
            neighbor = source + width
        start = flat_ids[source]
        end = flat_ids[neighbor]
        displacement = flat_points[neighbor] - flat_points[source]
        paired_slope = .5 * (flat_slope[source] + flat_slope[neighbor])
        target = _dot(displacement, paired_slope)
        local_area = .5 * (flat_area[source] + flat_area[neighbor])
        weight = local_area / np.maximum(_dot(displacement, displacement), 1e-12)
        weight = np.clip(weight, .02, 50)
        weight *= np.sqrt(flat_confidence[source] * flat_confidence[neighbor])
        diagonal[start] += weight
        diagonal[end] += weight
        rhs[start] -= weight * target
        rhs[end] += weight * target
        starts.append(start)
        ends.append(end)
        weights.append(weight.astype(np.float32))
    start, end, weight = map(np.concatenate, (starts, ends, weights))
    matrix = coo_matrix((-np.tile(weight, 2), (np.r_[start, end], np.r_[end, start])),
                        shape=(count, count)).tocsr() + diags(diagonal, format='csr')

    def check_iteration(_solution):
        if cancel_check is not None:
            cancel_check()

    # Aggregate the fine equation on 2x2 cells, including the same cuts and seam.
    coarse_shape = tuple((size + 1) // 2 for size in valid.shape)
    cell = (row // 2 * coarse_shape[1] + col // 2).astype(np.int32)
    parent_mask = np.bincount(cell, minlength=np.prod(coarse_shape)) > 0
    parent_ids = np.full(len(parent_mask), -1, dtype=np.int32)
    parent_ids[parent_mask] = np.arange(parent_mask.sum(), dtype=np.int32)
    parent = parent_ids[cell]
    a, b = parent[start], parent[end]
    boundary = a != b
    a, b, boundary_weight = a[boundary], b[boundary], weight[boundary]
    coarse_count = int(parent_mask.sum())
    coarse_diag = np.bincount(parent, minlength=coarse_count) * screen
    coarse_diag += np.bincount(a, weights=boundary_weight, minlength=coarse_count)
    coarse_diag += np.bincount(b, weights=boundary_weight, minlength=coarse_count)
    coarse_diag = coarse_diag.astype(np.float32)
    coarse_rhs = np.bincount(parent, weights=rhs, minlength=coarse_count).astype(np.float32)
    coarse_matrix = coo_matrix((-np.tile(boundary_weight, 2), (np.r_[a, b], np.r_[b, a])),
                               shape=(coarse_count, coarse_count)).tocsr() + diags(coarse_diag, format='csr')
    coarse, status = cg(coarse_matrix, coarse_rhs, M=diags(1 / coarse_diag, format='csr'), rtol=5e-4, maxiter=500, callback=check_iteration)
    if status < 0 or not np.isfinite(coarse).all():
        raise ValueError("Panorama coarse relief solve failed")
    field = np.zeros(len(parent_mask), dtype=np.float32)
    field[parent_mask] = coarse
    coords = ((row + .5) / 2 - .5, (col + .5) / 2 + .5)
    field = np.pad(field.reshape(coarse_shape), ((0, 0), (1, 1)), mode='wrap')
    support = np.pad(parent_mask.reshape(coarse_shape).astype(np.float32), ((0, 0), (1, 1)), mode='wrap')
    initial = map_coordinates(field, coords, order=1, mode='nearest')
    initial /= np.maximum(map_coordinates(support, coords, order=1, mode='nearest'), 1e-6)
    # The fine equation removes interpolation error and restores native slopes.
    result, status = cg(matrix, rhs, x0=initial, M=diags(1 / diagonal, format='csr'),
                        rtol=3e-5, maxiter=12, callback=check_iteration)
    if status < 0 or not np.isfinite(result).all():
        raise ValueError("Panorama fine relief solve failed")
    height = np.zeros(valid.shape, np.float32)
    height[row, col] = result
    return height


def refine_panorama_normals(depth, predicted, valid, *, detail_strength=1.0, cancel_check=None):
    """Recover terrain relief, its bake weights, and inward sphere sky normals."""
    if cancel_check is not None:
        cancel_check()
    if min(valid.shape) < 3 or not valid.any():
        return predicted, np.zeros(valid.shape, dtype=np.float32)
    cell_degrees = RELIEF_SCALE_DEGREES
    h, w = valid.shape
    theta = np.pi - 2 * np.pi * ((np.arange(w, dtype=np.float32) + .5) / w)
    phi = np.pi * ((np.arange(h, dtype=np.float32) + .5) / h)
    sin_theta, cos_theta = np.sin(theta)[None, :], np.cos(theta)[None, :]
    sin_phi, cos_phi = np.sin(phi)[:, None], np.cos(phi)[:, None]
    rays = np.stack((sin_phi * cos_theta, sin_phi * sin_theta, np.broadcast_to(cos_phi, (h, w))), -1)
    longitude = np.stack((sin_theta[0], -cos_theta[0], np.zeros(w, dtype=np.float32)), -1)[None, :]
    cell_pixels = cell_degrees * w / 360
    sigma = cell_pixels / 2.355
    kernel = _angular_kernel(w, sigma, sin_phi[:, 0])
    support = valid[..., None].astype(np.float32)
    smooth_support = np.maximum(_angular_blur(support, kernel, sigma), 1e-8)
    # Fit the base at the angular scale of the relief band.
    raw_log_depth = np.log(np.maximum(depth, 1e-6)).astype(np.float32)
    adjusted, caps = _polar_geometry(raw_log_depth, rays, valid, phi, cell_degrees)
    log_depth = (_angular_blur(adjusted[..., None] * support, kernel, sigma) / smooth_support)[..., 0]
    for radius, cap, plane in caps:
        _extend_polar_field(log_depth, radius, cap, plane)
    points = rays * np.exp(log_depth)[..., None]
    depth_edge_limit = min(.5, .08 * 4096 / w)
    horizontal = valid & np.roll(valid, -1, axis=1) & (abs(np.roll(raw_log_depth, -1, axis=1) - raw_log_depth) < depth_edge_limit)
    vertical = valid & np.roll(valid, -1, axis=0) & (abs(np.roll(raw_log_depth, -1, axis=0) - raw_log_depth) < depth_edge_limit)
    vertical[-1] = False
    reference, point_u, area = _normals(points, rays, horizontal, vertical)
    source_base = _unit(_angular_blur(predicted * support, kernel, sigma))
    slope, confidence = _tangent_slopes(predicted, rays, longitude, reference, point_u, source_base)
    # Integrate with a longer screening length so fine slopes keep their amplitude.
    height = _integrate(points, slope, confidence, valid, horizontal, vertical,
                        area, cell_pixels / np.pi, cancel_check)
    if cancel_check is not None:
        cancel_check()
    # Remove the coarse relief explicitly. The pointmap alone sets the base
    # surface while this periodic detail band carries the MoGe measurements.
    coarse = (_angular_blur(height[..., None], kernel, sigma) / smooth_support)[..., 0]
    height[valid] -= coarse[valid]
    # Pin relief and its slope at cuts and the poles. Compute the longitude buffer periodically.
    intact = valid & horizontal & np.roll(horizontal, 1, axis=1) & vertical & np.roll(vertical, 1, axis=0)
    distance = distance_transform_edt(np.pad(intact, ((0, 0), (4, 4)), mode='wrap'))[:, 4:-4]
    # A mesh cell of support gives the stronger relief room to flatten at cuts.
    taper = np.clip(distance / cell_pixels, 0, 1).astype(np.float32)
    # Near a silhouette, small normal offsets can fold the projected surface.
    facing = np.clip((-_dot(reference, rays) - .2) / .2, 0, 1)
    coverage = (taper * taper * (3 - 2 * taper)) * (facing * facing * (3 - 2 * facing))
    height *= coverage * detail_strength
    for radius, cap, _ in caps:
        _extend_polar_field(height, radius, cap, np.zeros_like(height))
    corrected_points = points + height[..., None] * reference
    corrected, _, _ = _normals(corrected_points, rays, horizontal, vertical)
    folded = _dot(corrected, reference) <= 0
    coverage[folded] = 0
    corrected[folded] = reference[folded]
    corrected[~valid] = -rays[~valid]
    if cancel_check is not None:
        cancel_check()
    return corrected, coverage

