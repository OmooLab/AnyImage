"""Extend Cutout texture boundaries along one structural inward direction."""

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from ...common.image import image_rgba


@dataclass(frozen=True)
class BoundaryMapping:
    target: tuple[np.ndarray, np.ndarray]
    source: tuple[np.ndarray, np.ndarray]


def build_boundary_mapping(mask, padding, target_shape):
    """Find source coordinates for the texels within the padded edge band."""
    height, width = target_shape
    source_height, source_width = mask.shape
    if (height, width) != mask.shape:
        y = np.arange(height) * source_height // height
        x = np.arange(width) * source_width // width
        mask = mask[y[:, None], x]
    if padding <= 0 or mask.all() or not mask.any():
        return None

    distance = padding * np.sqrt((height / source_height) * (width / source_width))
    signed = ndimage.distance_transform_edt(mask) - ndimage.distance_transform_edt(~mask)
    signed -= 0.5 * np.sign(signed)
    inward_y = ndimage.sobel(signed, axis=0, mode="nearest")
    inward_x = ndimage.sobel(signed, axis=1, mode="nearest")
    length = np.hypot(inward_y, inward_x)
    y, x = np.nonzero((abs(signed) <= distance) & (length > 1e-6))
    if not len(y):
        return None
    inward_y = inward_y[y, x] / length[y, x]
    inward_x = inward_x[y, x] / length[y, x]
    travel = distance - signed[y, x]
    entered = mask[y, x]
    active = np.ones_like(entered)
    last_y, last_x = y.astype(np.float32), x.astype(np.float32)
    step_count = int(np.ceil(travel.max() * 2))
    for step in range(1, step_count + 1):
        step_distance = np.minimum(step * 0.5, travel)
        sample_y = np.clip(y + inward_y * step_distance, 0.0, height - 1.0)
        sample_x = np.clip(x + inward_x * step_distance, 0.0, width - 1.0)
        row = np.rint(sample_y).astype(np.int64)
        column = np.rint(sample_x).astype(np.int64)
        inside = mask[row, column]
        update = active & inside
        last_y[update] = sample_y[update]
        last_x[update] = sample_x[update]
        entered |= update
        active &= ~entered | inside

    if not entered.any():
        return None
    return BoundaryMapping((y[entered], x[entered]), (last_y[entered], last_x[entered]))


def apply_boundary_mapping(values, mapping):
    """Sample all channels into mapped texels of a private image buffer."""
    for channel in range(values.shape[2]):
        plane = values[..., channel]
        plane[mapping.target] = ndimage.map_coordinates(
            plane, mapping.source, order=1, mode="nearest"
        )


def apply_depth_boundary_mapping(rgba, mapping, intrinsics):
    """Move camera Z and validity, then project target pixels onto their own rays."""
    camera = np.asarray(intrinsics, dtype=np.float32)
    if camera.shape != (3, 3) or camera[0, 0] <= 0.0 or camera[1, 1] <= 0.0:
        raise ValueError("Cutout Depth padding requires valid camera intrinsics")
    depth = ndimage.map_coordinates(rgba[..., 2], mapping.source, order=1, mode="nearest")
    validity = ndimage.map_coordinates(rgba[..., 3], mapping.source, order=1, mode="nearest")
    target_y, target_x = mapping.target
    usable = np.isfinite(depth) & (depth > 0.0) & np.isfinite(validity)
    target_y, target_x = target_y[usable], target_x[usable]
    depth, validity = depth[usable], validity[usable]
    rgba[target_y, target_x, 0] = (
        (target_x + 0.5 - camera[0, 2]) / camera[0, 0] * depth
    )
    rgba[target_y, target_x, 1] = (
        (target_y + 0.5 - camera[1, 2]) / camera[1, 1] * depth
    )
    rgba[target_y, target_x, 2] = depth
    rgba[target_y, target_x, 3] = validity


def pad_cutout_images(color_rgba, depth_image, intrinsics, mask, padding):
    """Apply the mesh's final mask to color and depth before material creation."""
    color_shape = color_rgba.shape[:2]
    mapping = build_boundary_mapping(mask, padding, color_shape)
    if mapping is not None:
        apply_boundary_mapping(color_rgba, mapping)
        if not np.isfinite(color_rgba).all():
            raise ValueError("Cutout texture padding produced invalid RGBA")

    if depth_image is None:
        return
    depth_shape = tuple(reversed(depth_image.size))
    if depth_shape != color_shape:
        mapping = build_boundary_mapping(mask, padding, depth_shape)
    depth = image_rgba(depth_image)
    if mapping is not None:
        apply_depth_boundary_mapping(depth, mapping, intrinsics)
        if not np.isfinite(depth).all():
            raise ValueError("Cutout texture padding produced invalid RGBA")
        depth_image.pixels.foreach_set(depth[::-1].ravel())
        depth_image.update()
    depth_image.pack()
    return depth
