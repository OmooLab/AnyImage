"""Verify boundary depth filtering before camera and radial projection."""

import bpy
import numpy as np
import pytest

from tests.support.depth_surface import evaluated
from tests.nodes.test_boundary_smoothing import boundary_neighbors, corner_mask, edge_band, uv_delta



def test_cutout_fine_outline_smooths_only_within_boundary_band():
    from tests.support.depth_surface import surface
    from anyimage.operators.cutout_tool.mesh import build_mesh

    obj, set_value = surface(step=0, resolution=8)
    yy, xx = np.mgrid[:32, :64]
    alpha = ((xx - 32)**2 / 27**2 + (yy - 16)**2 / 13**2 < 1).astype(float)
    points, faces, _, _, _ = build_mesh(alpha, 3, .9)
    obj.data.clear_geometry()
    obj.data.from_pydata([(x / 32, y / 32, 0) for x, y in points], [], faces.tolist())
    uv = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.new(name="UVMap")
    for loop in obj.data.loops:
        uv.data[loop.index].uv = points[loop.vertex_index] / (64, 32)
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], np.float32).reshape(32, 64, 4)
    pixels[..., 2] = 2 + 12 * ((xx > 25) & (xx < 39) & (yy > 25))
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Boundary Smooth", 0)
    before, original_faces = evaluated(obj)
    set_value("Boundary Smooth", 12)
    after, result_faces = evaluated(obj)
    assert result_faces == original_faces
    band = edge_band(original_faces, boundary_neighbors(original_faces))
    interior = [i for i in range(len(before)) if i not in band]
    assert interior
    np.testing.assert_array_equal(after[interior], before[interior])
    assert np.max(np.linalg.norm(after - before, axis=1)) > 1e-4
    set_value("Boundary Smooth", 0)
    np.testing.assert_array_equal(evaluated(obj)[0], before)


def test_plane_validity_hole_blurs_depth_and_protects_rectangle():
    from tests.support.planes import create_surface, evaluated as plane_mesh

    obj, set_value, _, _, image = create_surface("DEPTH")
    pixels = np.array(image.pixels[:], np.float32).reshape(8, 16, 4)
    pixels[..., 2] = 2
    pixels[2:6, 6:10, 3] = 0
    pixels[1:3, 7:9, 2] = 12
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    for name, value in (("Subdivide", 5), ("Depth Scale", 1)):
        set_value(name, value)
    before, faces, uv, *_ = plane_mesh(obj)
    set_value("Boundary Smooth", 12)
    after, result_faces, result_uv, *_ = plane_mesh(obj)
    assert faces == result_faces
    band = edge_band(faces, boundary_neighbors(faces))
    band_corners = corner_mask(faces, band)
    np.testing.assert_array_equal(result_uv[~band_corners], uv[~band_corners])
    uv_motion = np.linalg.norm(result_uv[band_corners] - uv[band_corners], axis=1)
    maximum_uv_motion = np.max(uv_motion)
    assert 1e-4 < maximum_uv_motion < 0.25, (
        maximum_uv_motion,
        np.max(np.abs(result_uv[band_corners] - uv[band_corners]), axis=0),
    )
    assert after[:, 1].max() < before[:, 1].max() - .1
    protected = np.any(np.isclose(uv, 0) | np.isclose(uv, 1), axis=1)
    corners = np.concatenate(faces)
    outer = np.unique(corners[protected])
    np.testing.assert_array_equal(after[outer], before[outer])
    # Position smoothing moves the cut band off its projection ray by design.
    band = edge_band(faces, boundary_neighbors(faces))
    kept = [i for i in range(len(before)) if i not in band]
    np.testing.assert_allclose(after[kept][:, [0, 2]] / (1.2 + after[kept][:, 1:2]),
                               before[kept][:, [0, 2]] / (1.2 + before[kept][:, 1:2]), atol=1e-6)
    set_value("Depth Mask", False)
    intact = plane_mesh(obj)[0]
    set_value("Boundary Smooth", 0)
    np.testing.assert_array_equal(plane_mesh(obj)[0], intact)


@pytest.mark.parametrize("region", ["seam", "pole"])
def test_panorama_blurs_opening_radially(region):
    from tests.nodes.test_image_depth_panorama import panorama, evaluated as panorama_mesh

    yy, xx = np.mgrid[:64, :128]
    distance = np.minimum(xx, 128 - xx)
    hole = (distance**2 + (yy - 32)**2 < 9**2) if region == "seam" else (yy > 54)
    spike = ((distance < 4) & (yy > 40) & (yy < 44)) if region == "seam" else ((yy > 50) & (xx < 8))
    depth = np.where(spike, 10., 3.)
    obj, set_value = panorama(depth, (~hole).astype(float), subdivide=5)
    before, faces, uv = panorama_mesh(obj)
    set_value("Boundary Smooth", 12)
    after, result_faces, result_uv = panorama_mesh(obj)
    assert result_faces == faces
    band = edge_band(faces, boundary_neighbors(faces))
    band_corners = corner_mask(faces, band)
    np.testing.assert_allclose(uv_delta(result_uv[~band_corners], uv[~band_corners]), 0, atol=1e-7)
    delta = uv_delta(result_uv[band_corners], uv[band_corners])
    assert np.max(np.linalg.norm(delta, axis=1)) > 1e-4
    if region == "seam":
        assert np.max(np.abs(delta[:, 0])) < 0.25
    radii = np.linalg.norm(before, axis=1)
    smoothed = np.linalg.norm(after, axis=1)
    rim = list(boundary_neighbors(faces))
    assert smoothed[rim].max() < radii[rim].max() - .1
    band = edge_band(faces, boundary_neighbors(faces))
    interior = [i for i in range(len(before)) if i not in band]
    assert interior
    # Position smoothing moves the opening rim off its radial direction by design.
    np.testing.assert_allclose(after[interior] / smoothed[interior, None],
                               before[interior] / radii[interior, None], atol=1e-6)
    np.testing.assert_array_equal(after[interior], before[interior])
