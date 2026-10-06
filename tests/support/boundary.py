"""Build and inspect depth boundaries, influence bands and corner UVs."""

from collections import Counter
import bpy
import bmesh
import numpy as np
from tests.support.depth_surface import surface


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
