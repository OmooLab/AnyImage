"""Verify split profile shaping and displacement direction shaping."""

import bpy
import numpy as np
import pytest

from tests.support.depth_surface import surface, evaluated
from tests.nodes.test_boundary_smoothing import diagonal_surface


def profile_values(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return np.array([v.value for v in mesh.attributes["o_balloon"].data])
    finally:
        result.to_mesh_clear()


def vertex_uv(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        uv = np.zeros((len(mesh.vertices), 2))
        for loop in mesh.loops:
            uv[loop.vertex_index] = mesh.uv_layers["UVMap"].data[loop.index].uv
        return uv
    finally:
        result.to_mesh_clear()


@pytest.mark.parametrize("iterations", [0, 16])
def test_cleaned_sawtooth_smoothing_preserves_face_orientation(iterations):
    obj, set_value = diagonal_surface(triangles=True)
    original, faces = evaluated(obj)
    set_value("Boundary Smooth", iterations)
    points, actual = evaluated(obj)
    assert actual == faces
    indices = np.array(faces)
    def normals(p):
        return np.cross(p[indices[:,1]]-p[indices[:,0]], p[indices[:,2]]-p[indices[:,0]])
    assert np.all(np.sum(normals(original)*normals(points), axis=1) > 0)


def test_split_profile_tapers_within_boundary_band():
    resolution, aspect = 12, .5
    obj, set_value = surface(step=6, resolution=resolution)
    for vertex in obj.data.vertices:
        vertex.co.x *= aspect
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], np.float32).reshape(32, 64, 4)
    pixels[..., 0] *= aspect
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    obj.data.attributes.new("o_balloon", "FLOAT", "POINT").data.foreach_set(
        "value", np.full(len(obj.data.vertices), .3, dtype=np.float32))
    set_value("Depth Scale", 1)
    np.testing.assert_allclose(profile_values(obj), .3)
    set_value("Depth Split", .1)
    values = profile_values(obj)
    uv = vertex_uv(obj)
    # The depth step sits at u=0.5, so only that column is tapered.
    cut = (np.abs(uv[:, 0] - .5) < 1e-4) & (uv[:, 1] > 1e-3) & (uv[:, 1] < 1 - 1e-3)
    assert cut.any()
    np.testing.assert_array_equal(values[cut], 0)
    untouched = (np.abs(uv[:, 0] - .25) < 1e-3) | (np.abs(uv[:, 0] - .75) < 1e-3)
    assert untouched.any()
    np.testing.assert_allclose(values[untouched], .3)
    assert np.isfinite(values).all()
    assert values.max() == pytest.approx(.3)
    set_value("Depth Split", 0)
    np.testing.assert_allclose(profile_values(obj), .3)
