"""Evaluate opposite-boundary cleanup on explicit mesh topology."""

import bpy
import bmesh
import numpy as np
import pytest

from nodes.common.depth_surface import _remove_triangle_strip_faces


@pytest.mark.parametrize("faces,retained", [
    pytest.param([], [], id="empty"),
    pytest.param([(0, 1, 2)], [], id="isolated-triangle"),
    pytest.param([(0, 1, 2), (0, 2, 3)], [], id="strip-pair"),
    pytest.param([(0, 1, 2), (3, 2, 0)], [], id="reversed-strip-pair"),
    pytest.param([(0, 1, 2), (1, 0, 3, 4)], [0, 1], id="triangle-next-to-quad"),
    pytest.param([(0, 1, 2), (1, 0, 3), (0, 1, 4)], [0, 1, 2], id="nonmanifold-edge"),
    pytest.param([(0, 1, 2), (2, 1, 0)], [0, 1], id="coincident-triangles"),
    pytest.param(
        [(0, 2, 4), (0, 1, 2), (2, 3, 4), (4, 5, 0)],
        [0, 1, 2, 3], id="boundary-vertices-without-boundary-strips",
    ),
])
def test_triangle_cleanup_preserves_unmatched_faces(faces, retained):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = bpy.data.node_groups.new("Triangle Cleanup", "GeometryNodeTree")
    for direction in ("INPUT", "OUTPUT"):
        group.interface.new_socket(
            name="Geometry", in_out=direction, socket_type="NodeSocketGeometry",
        )
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    geometry = _remove_triangle_strip_faces(group, source.outputs["Geometry"])
    group.links.new(geometry, output.inputs["Geometry"])
    angles = np.arange(6) * np.pi / 3
    mesh = bpy.data.meshes.new("Triangle Cleanup")
    mesh.from_pydata([(np.cos(a), np.sin(a), 0) for a in angles], [], faces)
    mesh.attributes.new("face_id", "INT", "FACE").data.foreach_set("value", np.arange(len(faces)))
    obj = bpy.data.objects.new("Triangle Cleanup", mesh)
    bpy.context.collection.objects.link(obj)
    obj.modifiers.new("Triangle Cleanup", "NODES").node_group = group
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = result.to_mesh()
    try:
        actual = [item.value for item in evaluated.attributes["face_id"].data] if evaluated.polygons else []
        assert actual == retained
    finally:
        result.to_mesh_clear()


@pytest.mark.parametrize("kind", ["plane", "cutout"])
def test_strips_are_removed_before_projection(kind):
    from tests.support.depth_surface import surface, evaluated
    from tests.support.planes import create_surface

    if kind == "plane":
        obj, set_value, _, _, image = create_surface("DEPTH")
        set_value("Subdivide", 1)
    else:
        obj, set_value = surface(step=0.0)
        image = bpy.data.images["Camera"]
    width, height = image.size
    pixels = np.array(image.pixels[:], np.float32).reshape(height, width, 4)
    pixels[..., 2] = 1
    pixels[:, width // 4:3 * width // 4, 2] = 21
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Scale", 1.0)
    set_value("Reference Depth", 11.0)
    if kind == "cutout":
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
        assert len(evaluated(obj)[1]) == 14
    else:
        assert len(evaluated(obj)[1]) == 8
    set_value("Depth Split", 0.5)
    vertices, faces = evaluated(obj)
    if kind == "cutout":
        assert len(faces) == 6 and len(vertices) == 7
    else:
        assert len(faces) == 4 and len(vertices) == 9
    assert np.isfinite(vertices).all()


def test_zero_split_bypasses_cleanup_and_positive_split_can_empty_mesh():
    from tests.support.depth_surface import evaluated
    from tests.support.planes import create_surface

    obj, set_value, _, _, _ = create_surface("DEPTH")
    set_value("Subdivide", 0)
    set_value("Depth Scale", 1.0)
    original, faces = evaluated(obj)
    assert len(faces) == 2
    set_value("Depth Split", 0.001)
    assert not evaluated(obj)[1]
    set_value("Thickness", 0.2)
    assert not evaluated(obj)[1]
    set_value("Thickness", 0.0)
    set_value("Depth Split", 0.0)
    restored, restored_faces = evaluated(obj)
    assert restored_faces == faces
    np.testing.assert_array_equal(restored, original)
