"""Behavior checks for face separation and connected Depth Surface shells."""

from collections import Counter
import bpy
import numpy as np


from tests.support.nodes import CUTOUT_BUILDERS


def surface(*, step=6.0, size=1.0, resolution=2):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = CUTOUT_BUILDERS["DEPTH_SOLID"]()
    # Two columns with a complete depth jump along their common boundary.
    points = [
        (x * size / resolution, 0, y * size / resolution)
        for y in range(resolution + 1)
        for x in range(2 * resolution + 1)
    ]
    stride = 2 * resolution + 1
    faces = [
        (
            y * stride + x,
            y * stride + x + 1,
            (y + 1) * stride + x + 1,
            (y + 1) * stride + x,
        )
        for y in range(resolution)
        for x in range(2 * resolution)
    ]
    mesh = bpy.data.meshes.new("Step")
    mesh.from_pydata(points, [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        x, _y, z = points[loop.vertex_index]
        uv.data[loop.index].uv = (x / (2 * size), z / size)
    obj = bpy.data.objects.new("Step", mesh)
    bpy.context.collection.objects.link(obj)
    image = bpy.data.images.new("Camera", width=64, height=32, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    yy, xx = np.mgrid[:32, :64]
    pixels = np.ones((32, 64, 4), np.float32)
    pixels[..., 0] = (xx + 0.5) / 32
    pixels[..., 1] = -(yy + 0.5) / 32
    pixels[..., 2] = 1 + (xx >= 32) * step
    image.pixels.foreach_set(pixels.ravel())
    modifier = obj.modifiers.new("Depth Surface", "NODES")
    modifier.node_group = group
    inputs = {
        s.name: s.identifier
        for s in group.interface.items_tree
        if s.item_type == "SOCKET" and s.in_out == "INPUT"
    }

    def set_value(name, value):
        modifier[inputs[name]] = value
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()

    for name, value in (
        ("Depth Image", image),
        ("Uniform Scale", size),
        ("Reference Depth", size * (1 + step / 2)),
        ("Depth Scale", 1.0),
        ("Thickness", 0.0),
        ("Front Inflation", 0.0),
        ("Depth Split", 0.0),
        ("Mode", 1),
        ("Boundary Smooth", 0),
    ):
        set_value(name, value)
    return obj, set_value


def evaluated(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        return np.array([v.co[:] for v in mesh.vertices]), [
            tuple(p.vertices) for p in mesh.polygons
        ]
    finally:
        result.to_mesh_clear()


def assert_closed(faces):
    edges = Counter(
        tuple(sorted((a, b))) for f in faces for a, b in zip(f, (*f[1:], f[0]))
    )
    assert edges and set(edges.values()) == {2}, Counter(edges.values())


def assert_single_vertex_fans(faces):
    """Every vertex must close one face fan so touching sheets stay identifiable."""
    incident = {}
    for index, face in enumerate(faces):
        for start, end in zip(face, (*face[1:], face[0])):
            edge = tuple(sorted((start, end)))
            incident.setdefault(start, {}).setdefault(edge, []).append(index)
            incident.setdefault(end, {}).setdefault(edge, []).append(index)
    for vertex, edges in incident.items():
        shared = {}
        for faces_at_edge in edges.values():
            assert len(faces_at_edge) == 2, (vertex, faces_at_edge)
            first, second = faces_at_edge
            shared.setdefault(first, set()).add(second)
            shared.setdefault(second, set()).add(first)
        assert all(len(neighbors) == 2 for neighbors in shared.values()), vertex
        reached, pending = {next(iter(shared))}, [next(iter(shared))]
        while pending:
            for neighbor in shared[pending.pop()] - reached:
                reached.add(neighbor)
                pending.append(neighbor)
        assert len(reached) == len(shared), vertex


def component_count(faces):
    adjacency = {}
    for face in faces:
        for a, b in zip(face, (*face[1:], face[0])):
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    remaining = set(adjacency)
    count = 0
    while remaining:
        count += 1
        pending = [remaining.pop()]
        while pending:
            for neighbor in adjacency[pending.pop()] & remaining:
                remaining.remove(neighbor)
                pending.append(neighbor)
    return count
