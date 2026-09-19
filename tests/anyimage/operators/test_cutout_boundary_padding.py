import numpy as np

from anyimage.operators.cutout_tool.boundary_padding import (
    apply_boundary_mapping,
    apply_depth_boundary_mapping,
    build_boundary_mapping,
    image_rgba_buffer,
    pad_cutout_images,
)


def square_with_hole():
    values = np.zeros((17, 17), dtype=np.float32)
    values[3:14, 3:14] = 1
    values[7:10, 7:10] = 0
    return values


def test_outer_and_hole_boundaries_follow_the_local_interior():
    mapping = build_boundary_mapping(square_with_hole(), 0.9, 2)
    assert mapping.target[2, 8]
    assert mapping.source_y[2, 8] > 3
    assert abs(mapping.source_x[2, 8] - 8) < 0.25
    assert mapping.target[7, 8]
    assert mapping.source_y[7, 8] < 7
    assert abs(mapping.source_x[7, 8] - 8) < 0.5


def test_mapping_moves_along_one_direction_instead_of_nearest_content():
    values = square_with_hole()
    yy, xx = np.mgrid[:17, :17]
    rgba = np.stack((xx, yy, xx + yy, np.ones_like(xx)), axis=-1).astype(np.float32)
    mapping = build_boundary_mapping(values, 0.9, 3)
    result = apply_boundary_mapping(rgba, mapping)
    assert result[1, 8, 1] > 3
    assert abs(result[1, 8, 0] - 8) < 0.5


def test_boundary_mapping_aligns_inner_and_outer_source_coordinates():
    values = np.zeros((9, 9), dtype=np.float32)
    values[3:6, 3:6] = 1.0

    mapping = build_boundary_mapping(values, 0.9, 2)

    np.testing.assert_allclose(
        mapping.source_x[4, 2],
        mapping.source_x[4, 3],
        atol=0.25,
    )


def test_thin_structure_stops_at_the_last_point_on_the_same_ray():
    values = np.zeros((11, 15), dtype=np.float32)
    values[5:7, 2:13] = 1
    mapping = build_boundary_mapping(values, 0.9, 4)
    sampled_inside = values[
        np.rint(mapping.source_y[mapping.target]).astype(int),
        np.rint(mapping.source_x[mapping.target]).astype(int),
    ]
    assert sampled_inside.size
    assert np.all(sampled_inside == 1)
    assert np.isfinite(mapping.source_y).all()
    assert np.isfinite(mapping.source_x).all()


def test_scaled_mapping_uses_proportional_padding_and_zero_is_identity():
    values = square_with_hole()
    original = build_boundary_mapping(values, 0.9, 2)
    scaled = build_boundary_mapping(values, 0.9, 2, (34, 34))
    assert scaled.target.sum() > original.target.sum() * 3
    disabled = build_boundary_mapping(values, 0.9, 0)
    assert not disabled.target.any()


def test_depth_moves_z_and_validity_but_reprojects_xy_on_target_rays():
    values = np.zeros((9, 9), dtype=np.float32)
    values[2:7, 2:7] = 1
    mapping = build_boundary_mapping(values, 0.9, 2)
    yy, xx = np.mgrid[:9, :9]
    rgba = np.zeros((9, 9, 4), dtype=np.float32)
    rgba[..., 2] = yy + 10
    rgba[..., 3] = yy / 10
    intrinsics = np.array(((4, 0, 4), (0, 4, 4), (0, 0, 1)), dtype=np.float32)
    result = apply_depth_boundary_mapping(rgba, mapping, intrinsics)
    y, x = 1, 4
    assert mapping.target[y, x]
    assert result[y, x, 2] > rgba[2, x, 2]
    assert result[y, x, 0] == 0
    assert result[y, x, 1] == (y - 4) / 4 * result[y, x, 2]
    assert result[y, x, 3] > rgba[2, x, 3]


class PixelBuffer:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.float32).copy()

    def foreach_get(self, target):
        target[:] = self.values

    def foreach_set(self, values):
        self.values[:] = values


class Image:
    def __init__(self, top_down):
        height, width = top_down.shape[:2]
        self.size = (width, height)
        self.pixels = PixelBuffer(np.flipud(top_down).ravel())
        self.updated = 0
        self.packed = 0

    def update(self):
        self.updated += 1

    def pack(self):
        self.packed += 1


def test_client_processing_updates_and_packs_color_and_depth_together():
    content = square_with_hole()
    yy, xx = np.mgrid[:17, :17]
    color_values = np.stack((xx, yy, xx + yy, content), axis=-1).astype(np.float32)
    original = color_values.copy()
    color = Image(color_values)
    depth_values = np.zeros((17, 17, 4), dtype=np.float32)
    depth_values[..., 2] = yy + 10
    depth_values[..., 3] = content
    depth = Image(depth_values)
    metadata = {
        "intrinsics": ((8.0, 0.0, 8.0), (0.0, 8.0, 8.0), (0.0, 0.0, 1.0)),
    }
    original_metadata = dict(metadata)

    pad_cutout_images(color, depth, metadata, content, 0.9, 2)

    padded_color = image_rgba_buffer(color)
    padded_depth = image_rgba_buffer(depth)
    np.testing.assert_array_equal(padded_color[5, 5], original[5, 5])
    assert padded_color[2, 8, 3] == 1
    assert padded_depth[2, 8, 2] > depth_values[3, 8, 2]
    assert padded_depth[2, 8, 0] == 0
    assert metadata == original_metadata
    assert (color.updated, color.packed, depth.updated, depth.packed) == (1, 1, 1, 1)
