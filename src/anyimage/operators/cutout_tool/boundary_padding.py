"""Extend Cutout texture boundaries along one structural inward direction."""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class BoundaryMapping:
    target: object
    source_y: object
    source_x: object


def _resized_mask(content_values, threshold, target_shape):
    values = np.asarray(content_values, dtype=np.float32)
    if values.ndim != 2 or not values.size or not np.isfinite(values).all():
        raise ValueError("Cutout content values must be a finite two-dimensional array")
    target_height, target_width = (int(value) for value in target_shape)
    if target_height <= 0 or target_width <= 0:
        raise ValueError("Cutout padding target dimensions must be positive")
    source_height, source_width = values.shape
    y = np.minimum(
        (np.arange(target_height) * source_height / target_height).astype(np.int64),
        source_height - 1,
    )
    x = np.minimum(
        (np.arange(target_width) * source_width / target_width).astype(np.int64),
        source_width - 1,
    )
    return values[y[:, None], x[None, :]] >= float(threshold)


def build_boundary_mapping(content_values, threshold, padding, target_shape=None):
    """Map a boundary band to one fixed-distance sample along its inward normal."""
    values = np.asarray(content_values, dtype=np.float32)
    shape = values.shape if target_shape is None else tuple(target_shape)
    mask = _resized_mask(values, threshold, shape)
    height, width = mask.shape
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    source_y, source_x = yy.copy(), xx.copy()
    padding = float(padding)
    if not np.isfinite(padding) or padding < 0.0:
        raise ValueError("Cutout Boundary Padding must be finite and nonnegative")
    if padding == 0.0 or not mask.any() or mask.all():
        return BoundaryMapping(np.zeros(mask.shape, dtype=bool), source_y, source_x)

    scale = np.sqrt(
        (height / values.shape[0]) * (width / values.shape[1])
    )
    distance = padding * scale
    signed = ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)
    signed = np.where(signed != 0.0, signed - 0.5 * np.sign(signed), 0.0)
    inward_y = ndimage.sobel(signed, axis=0, mode="nearest")
    inward_x = ndimage.sobel(signed, axis=1, mode="nearest")
    length = np.hypot(inward_y, inward_x)
    defined = np.isfinite(length) & (length > 1e-6)
    inward_y = np.divide(inward_y, length, out=np.zeros_like(inward_y), where=defined)
    inward_x = np.divide(inward_x, length, out=np.zeros_like(inward_x), where=defined)
    band = (signed >= -distance) & (signed <= distance) & defined
    travel = np.maximum(distance - signed, 0.0)

    entered = mask & band
    active = band.copy()
    last_y, last_x = source_y.copy(), source_x.copy()
    step_count = max(1, int(np.ceil(float(travel[band].max(initial=0.0)) * 2.0)))
    for step in range(1, step_count + 1):
        step_distance = np.minimum(step * 0.5, travel)
        sample_y = np.clip(yy + inward_y * step_distance, 0.0, height - 1.0)
        sample_x = np.clip(xx + inward_x * step_distance, 0.0, width - 1.0)
        row = np.rint(sample_y).astype(np.int64)
        column = np.rint(sample_x).astype(np.int64)
        inside = mask[row, column]
        update = active & inside
        last_y[update] = sample_y[update]
        last_x[update] = sample_x[update]
        entered |= update
        active &= ~entered | inside

    target = band & entered
    source_y[target] = last_y[target]
    source_x[target] = last_x[target]
    return BoundaryMapping(target, source_y, source_x)


def apply_boundary_mapping(values, mapping):
    """Sample all channels at mapped coordinates while preserving other pixels."""
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 3 or array.shape[:2] != mapping.target.shape:
        raise ValueError("Cutout texture values do not match the boundary mapping")
    result = array.copy()
    if not mapping.target.any():
        return result
    coordinates = (mapping.source_y[mapping.target], mapping.source_x[mapping.target])
    for channel in range(array.shape[2]):
        result[..., channel][mapping.target] = ndimage.map_coordinates(
            array[..., channel], coordinates, order=1, mode="nearest"
        )
    return result


def apply_depth_boundary_mapping(rgba, mapping, intrinsics):
    """Move camera Z and validity, then project target pixels onto their own rays."""
    array = np.asarray(rgba, dtype=np.float32)
    if array.ndim != 3 or array.shape[2] != 4 or array.shape[:2] != mapping.target.shape:
        raise ValueError("Cutout Depth values do not match the boundary mapping")
    camera = np.asarray(intrinsics, dtype=np.float32)
    if camera.shape != (3, 3) or camera[0, 0] <= 0.0 or camera[1, 1] <= 0.0:
        raise ValueError("Cutout Depth padding requires valid camera intrinsics")
    result = array.copy()
    if not mapping.target.any():
        return result
    coordinates = (mapping.source_y[mapping.target], mapping.source_x[mapping.target])
    depth = ndimage.map_coordinates(array[..., 2], coordinates, order=1, mode="nearest")
    validity = ndimage.map_coordinates(array[..., 3], coordinates, order=1, mode="nearest")
    target_y, target_x = np.nonzero(mapping.target)
    usable = np.isfinite(depth) & (depth > 0.0) & np.isfinite(validity)
    target_y, target_x = target_y[usable], target_x[usable]
    depth, validity = depth[usable], validity[usable]
    result[target_y, target_x, 0] = (
        (target_x - camera[0, 2]) / camera[0, 0] * depth
    )
    result[target_y, target_x, 1] = (
        (target_y - camera[1, 2]) / camera[1, 1] * depth
    )
    result[target_y, target_x, 2] = depth
    result[target_y, target_x, 3] = validity
    return result


def image_rgba_buffer(image):
    """Read one Blender Image buffer as a top-down RGBA array without reinterpretation."""
    width, height = (int(value) for value in image.size)
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return np.flipud(pixels.reshape((height, width, 4)))


def write_image_rgba_buffer(image, rgba):
    """Replace and pack one Blender Image buffer."""
    values = np.asarray(rgba, dtype=np.float32)
    width, height = (int(value) for value in image.size)
    if values.shape != (height, width, 4) or not np.isfinite(values).all():
        raise ValueError("Cutout texture padding produced invalid RGBA")
    image.pixels.foreach_set(np.flipud(values).ravel())
    image.update()
    image.pack()


def pad_cutout_images(
    color_image,
    depth_image,
    depth_metadata,
    content_values,
    alpha_threshold,
    padding,
):
    """Apply one structural Cutout boundary rule before image consumption."""
    padding = float(padding)
    if padding <= 0.0:
        return
    color = image_rgba_buffer(color_image)
    color_mapping = build_boundary_mapping(
        content_values, alpha_threshold, padding, color.shape[:2]
    )
    write_image_rgba_buffer(color_image, apply_boundary_mapping(color, color_mapping))
    if depth_image is None:
        return
    depth = image_rgba_buffer(depth_image)
    depth_mapping = build_boundary_mapping(
        content_values, alpha_threshold, padding, depth.shape[:2]
    )
    write_image_rgba_buffer(
        depth_image,
        apply_depth_boundary_mapping(depth, depth_mapping, depth_metadata["intrinsics"]),
    )
