"""Check symmetry cleanup on triangles, quads and partial n-gon boundaries."""

import bpy
import numpy as np
import pytest

from nodes.groups import image_cutout_symmetry as symmetry


@pytest.mark.parametrize("kind,faces,retained", [
    pytest.param("bridge", [(0, 1, 2)], [], id="triangle"),
    pytest.param("bridge", [(0, 1, 2, 3)], [], id="quad"),
    pytest.param("bridge", [tuple(range(6))], [], id="hexagon"),
    pytest.param(
        "bridge", [tuple(range(6))] + [(i, (i + 1) % 6, 6 + i) for i in range(4)],
        [0], id="boundary-after-fourth-edge",
    ),
    pytest.param(
        "crease", [tuple(range(6)), (4, 5, 6)], [0],
        id="crease-after-fourth-edge",
    ),
    pytest.param(
        "crease", [tuple(range(6)), (0, 1, 6)], [],
        id="crease-within-first-four-edges",
    ),
])
def test_cleanup_preserves_first_four_edge_selection(kind, faces, retained):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = bpy.data.node_groups.new("Symmetry Cleanup", "GeometryNodeTree")
    for direction in ("INPUT", "OUTPUT"):
        symmetry.interface_socket(group, "Geometry", direction, "NodeSocketGeometry")
    geometry = group.nodes.new("NodeGroupInput").outputs["Geometry"]
    face_count = group.nodes.new("GeometryNodeInputMeshEdgeNeighbors").outputs["Face Count"]
    face_edges = symmetry._face_edge_fields(group)
    if kind == "bridge":
        boundary = symmetry.compare_node(group, "EQUAL", face_count, 1, data_type="INT")
        geometry = symmetry._delete_bridge_faces(group, geometry, boundary, face_edges)
    else:
        height = symmetry._math(group, "MAXIMUM", *symmetry._edge_abs_y(group))
        geometry = symmetry._delete_crease_faces(
            group, geometry, height, face_count, face_edges, 1e-6,
        )
    group.links.new(geometry, group.nodes.new("NodeGroupOutput").inputs["Geometry"])
    angles = np.arange(6) * np.pi / 3
    points = [(np.cos(a), 0, np.sin(a)) for a in angles]
    points.extend((3 + i, 0, 3) for i in range(4))
    mesh = bpy.data.meshes.new("Symmetry Cleanup")
    mesh.from_pydata(points, [], faces)
    mesh.attributes.new("face_id", "INT", "FACE").data.foreach_set("value", np.arange(len(faces)))
    obj = bpy.data.objects.new("Symmetry Cleanup", mesh)
    bpy.context.collection.objects.link(obj)
    obj.modifiers.new("Symmetry Cleanup", "NODES").node_group = group
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        actual = [item.value for item in mesh.attributes["face_id"].data] if mesh.polygons else []
        assert actual == retained
    finally:
        result.to_mesh_clear()
