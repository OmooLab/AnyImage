"""Verify pinned-boundary smoothing stays within its fixed edge band."""

from collections import Counter

import bpy
import bmesh
import numpy as np

from tests.support.depth_surface import surface, evaluated, assert_closed


def diagonal_surface(triangles=False):
    obj, set_value = surface(resolution=16)
    if triangles:
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        bmesh.ops.triangulate(mesh, faces=list(mesh.faces))
        mesh.to_mesh(obj.data)
        mesh.free()
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], np.float32).reshape(32, 64, 4)
    yy, xx = np.mgrid[:32, :64]
    pixels[..., 2] = 1 + (xx > 18 + yy * 0.7) * 6
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Split", 0.5)
    # A shallow display keeps the cut nearly flat so smoothing cannot fold the
    # sawtooth slivers this fixture exists to exercise.
    set_value("Depth Scale", 0.05)
    return obj, set_value


def boundary_neighbors(faces):
    edges = Counter(tuple(sorted((a, b))) for face in faces for a, b in zip(face, (*face[1:], face[0])))
    neighbors = {}
    for (a, b), count in edges.items():
        if count == 1:
            neighbors.setdefault(a, []).append(b)
            neighbors.setdefault(b, []).append(a)
    return neighbors


def edge_band(faces, seeds, rings=2):
    adjacency = {}
    for face in faces:
        for a, b in zip(face, (*face[1:], face[0])):
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    selected = set(seeds)
    for _ in range(rings):
        selected |= {neighbor for vertex in selected for neighbor in adjacency[vertex]}
    return selected


def vertex_uv(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        values = np.zeros((len(mesh.vertices), 2))
        for loop in mesh.loops:
            values[loop.vertex_index] = mesh.uv_layers["UVMap"].data[loop.index].uv
        return values
    finally:
        result.to_mesh_clear()


def corner_mask(faces, vertices):
    return np.isin(np.concatenate(faces), np.fromiter(vertices, dtype=np.int64))


def uv_delta(after, before):
    delta = after - before
    delta[:, 0] -= np.round(delta[:, 0])
    return delta


def test_cutout_boundary_smooth_defaults_to_four():
    obj, _ = surface()
    socket = next(
        item for item in obj.modifiers[0].node_group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT" and item.name == "Boundary Smooth"
    )
    assert socket.default_value == 4
    assert (socket.min_value, socket.max_value) == (0, 16)


def test_smoothing_reduces_stairs_without_leaving_two_ring_band():
    obj, set_value = diagonal_surface(triangles=True)
    original, faces = evaluated(obj)
    original_uv = vertex_uv(obj)
    boundary = boundary_neighbors(faces)
    outer = np.isclose(original[:, 0], 0) | np.isclose(original[:, 0], 2)
    outer |= np.isclose(original[:, 2], 0) | np.isclose(original[:, 2], 1)
    cut = {i for i in boundary if not outer[i]}
    band = edge_band(faces, boundary)
    movable = np.array([i in band for i in range(len(original))])
    assert movable.any() and (~movable).any()
    set_value("Boundary Smooth", 16)
    smoothed, result_faces = evaluated(obj)
    smoothed_uv = vertex_uv(obj)
    assert result_faces == faces
    np.testing.assert_array_equal(smoothed[~movable], original[~movable])
    np.testing.assert_array_equal(smoothed_uv[~movable], original_uv[~movable])
    assert np.max(np.linalg.norm(smoothed - original, axis=1)) > 0.005
    uv_motion = np.linalg.norm(smoothed_uv[movable] - original_uv[movable], axis=1)
    maximum_uv_motion = np.max(uv_motion)
    assert 1e-4 < maximum_uv_motion < 0.25, (
        maximum_uv_motion, np.max(np.abs(smoothed_uv[movable] - original_uv[movable]), axis=0)
    )
    nearby = [i for i in band if i not in boundary and not outer[i]]
    assert np.max(np.linalg.norm(smoothed[nearby] - original[nearby], axis=1)) > 1e-4
    before, after = [], []
    for i in cut:
        adjacent = boundary[i]
        if len(adjacent) != 2:
            continue
        before.append(np.linalg.norm(original[adjacent].mean(axis=0) - original[i]))
        after.append(np.linalg.norm(smoothed[adjacent].mean(axis=0) - smoothed[i]))
    assert sum(after) < 0.8 * sum(before)
    set_value("Boundary Smooth", 0)
    np.testing.assert_array_equal(evaluated(obj)[0], original)
    np.testing.assert_array_equal(vertex_uv(obj), original_uv)


def test_smoothing_without_split_moves_outline_only_within_boundary_band():
    obj, set_value = diagonal_surface()
    set_value("Depth Split", 0)
    original, faces = evaluated(obj)
    set_value("Boundary Smooth", 16)
    result, result_faces = evaluated(obj)
    boundary = boundary_neighbors(faces)
    band = edge_band(faces, boundary)
    outside = [i for i in range(len(original)) if i not in band]
    assert np.max(np.linalg.norm(result[list(boundary)] - original[list(boundary)], axis=1)) > 1e-4
    np.testing.assert_array_equal(result[outside], original[outside])
    assert result_faces == faces
    set_value("Boundary Smooth", 0)
    np.testing.assert_array_equal(evaluated(obj)[0], original)


def test_panorama_smoothing_relaxes_boundary_uvs_only():
    from tests.nodes.test_image_depth_panorama import panorama, evaluated as panorama_mesh

    yy, xx = np.mgrid[:64, :128]
    depth = np.where(xx > 35 + yy * 0.6, 8.0, 2.0)
    obj, set_value = panorama(depth, subdivide=4)
    set_value("Depth Split", 0.5)
    original, faces, uv = panorama_mesh(obj)
    rim = boundary_neighbors(faces)
    band = edge_band(faces, rim)
    interior = [i for i in range(len(original)) if i not in band]
    set_value("Boundary Smooth", 4)
    result, result_faces, result_uv = panorama_mesh(obj)
    assert np.isfinite(result).all()
    assert result_faces == faces
    np.testing.assert_array_equal(result[interior], original[interior])
    band_corners = corner_mask(faces, band)
    np.testing.assert_allclose(uv_delta(result_uv[~band_corners], uv[~band_corners]), 0, atol=1e-7)
    assert np.max(np.linalg.norm(uv_delta(result_uv[band_corners], uv[band_corners]), axis=1)) > 1e-4
    assert np.max(np.linalg.norm(result-original, axis=1)) > 1e-4


def test_plane_edge_smoothing_relaxes_uvs_and_closes_thickness():
    from tests.support.planes import create_surface, evaluated as plane_mesh

    obj, set_value, _, inputs, image = create_surface("DEPTH")
    assert inputs["Boundary Smooth"].default_value == 4
    assert inputs["Boundary Smooth"].parent.name == "Options"
    pixels = np.array(image.pixels[:], np.float32).reshape(8, 16, 4)
    yy, xx = np.mgrid[:8, :16]
    pixels[..., 2] = 1 + (xx > 5 + yy * 0.7) * 6
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Subdivide", 5)
    set_value("Depth Scale", 1)
    set_value("Depth Split", 0.5)
    original, faces, uv, *_ = plane_mesh(obj)
    set_value("Boundary Smooth", 4)
    result, result_faces, result_uv, *_ = plane_mesh(obj)
    assert result_faces == faces
    boundary = boundary_neighbors(faces)
    band = edge_band(faces, boundary)
    band_corners = corner_mask(faces, band)
    np.testing.assert_array_equal(result_uv[~band_corners], uv[~band_corners])
    uv_motion = np.linalg.norm(result_uv[band_corners] - uv[band_corners], axis=1)
    maximum_uv_motion = np.max(uv_motion)
    assert 1e-4 < maximum_uv_motion < 0.25, (
        maximum_uv_motion,
        np.max(np.abs(result_uv[band_corners] - uv[band_corners]), axis=0),
    )
    assert np.max(np.linalg.norm(result-original, axis=1)) > 1e-4
    set_value("Thickness", 0.03)
    assert_closed(plane_mesh(obj)[1])


def test_validity_cut_smoothing_preserves_original_outline_and_interior():
    from tests.support.planes import create_surface, evaluated as plane_mesh

    obj, set_value, _, _, image = create_surface("DEPTH")
    set_value("Subdivide", 5)
    set_value("Depth Split", 0)
    set_value("Depth Mask", False)
    whole = plane_mesh(obj)[0]
    low, high = whole.min(axis=0), whole.max(axis=0)
    pixels = np.array(image.pixels[:], np.float32).reshape(8, 16, 4)
    yy, xx = np.mgrid[:8, :16]
    pixels[..., 3] = xx < 5 + yy * 0.7
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Mask", True)
    before, faces, uv, *_ = plane_mesh(obj)
    boundary = boundary_neighbors(faces)
    outer = np.any(np.isclose(before[:, [0, 2]], low[[0, 2]]) | np.isclose(before[:, [0, 2]], high[[0, 2]]), axis=1)
    cut = {i for i in boundary if not outer[i]}
    band = edge_band(faces, cut)
    fixed = np.array([i not in band or outer[i] for i in range(len(before))])
    set_value("Boundary Smooth", 5)
    after, result_faces, result_uv, *_ = plane_mesh(obj)
    assert result_faces == faces
    fixed_corners = corner_mask(faces, np.flatnonzero(fixed))
    np.testing.assert_array_equal(result_uv[fixed_corners], uv[fixed_corners])
    assert np.max(np.linalg.norm(result_uv[~fixed_corners] - uv[~fixed_corners], axis=1)) > 1e-4
    np.testing.assert_array_equal(after[fixed], before[fixed])
    assert np.max(np.linalg.norm(after-before, axis=1)) > 1e-4
    before_bends, after_bends = [], []
    for i in cut:
        if len(boundary[i]) == 2:
            before_bends.append(np.linalg.norm(before[boundary[i]].mean(axis=0)-before[i]))
            after_bends.append(np.linalg.norm(after[boundary[i]].mean(axis=0)-after[i]))
    assert sum(after_bends) < sum(before_bends) * 0.8
    set_value("Thickness", 0.03)
    assert_closed(plane_mesh(obj)[1])
    set_value("Thickness", 0)
    set_value("Depth Mask", False)
    np.testing.assert_array_equal(plane_mesh(obj)[0], whole)


def test_panorama_validity_cut_smoothing_stays_in_two_ring_band():
    from tests.nodes.test_image_depth_panorama import panorama, evaluated as panorama_mesh

    yy, xx = np.mgrid[:64, :128]
    alpha = ((xx-64)**2 + (yy-32)**2 > 15**2).astype(np.float32)
    obj, set_value = panorama(np.full((64, 128), 3), alpha, subdivide=4)
    set_value("Depth Split", 0)
    before, faces, uv = panorama_mesh(obj)
    band = edge_band(faces, boundary_neighbors(faces))
    outside = [i for i in range(len(before)) if i not in band]
    set_value("Boundary Smooth", 5)
    after, result_faces, result_uv = panorama_mesh(obj)
    assert result_faces == faces
    band_corners = corner_mask(faces, band)
    np.testing.assert_allclose(uv_delta(result_uv[~band_corners], uv[~band_corners]), 0, atol=1e-7)
    assert np.max(np.linalg.norm(uv_delta(result_uv[band_corners], uv[band_corners]), axis=1)) > 1e-4
    np.testing.assert_array_equal(after[outside], before[outside])
    assert np.max(np.linalg.norm(after-before, axis=1)) > 1e-4
