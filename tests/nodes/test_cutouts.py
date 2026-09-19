from collections import Counter

import bpy

import numpy as np
import pytest
from nodes.groups.image_cutout import build_image_cutout_group
from tests.support.nodes import CUTOUT_BUILDERS


from anyimage.common.object import modifier_input_identifier, set_modifier_input


@pytest.mark.parametrize("shape", ("SOLID", "DEPTH_SOLID"))
def test_depth_axis_is_removed_from_cutout_options(shape):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = CUTOUT_BUILDERS[shape]()
    inputs = {item.name: item for item in group.interface.items_tree
              if item.item_type == "SOCKET" and item.in_out == "INPUT"}
    assert "Depth Axis" not in inputs
    assert "Inward Axis" not in inputs
    assert all(item.name != "Depth Axis" for item in group.interface.items_tree)


def test_cutout_thickness_modes():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("Profile")
    mesh.from_pydata([(-1,0,-1), (1,0,-1), (1,0,1), (-1,0,1), (0,0,0)], [], [(0,1,4), (1,2,4), (2,3,4), (3,0,4)])
    profile = mesh.attributes.new("o_balloon", "FLOAT", "POINT")
    profile.data.foreach_set("value", [0,0,0,0,0.6])
    obj = bpy.data.objects.new("Profile", mesh)
    bpy.context.collection.objects.link(obj)
    modifier = obj.modifiers.new("Cutout", "NODES")
    modifier.node_group = build_image_cutout_group()
    for mode, thickness in ((0, 0), (0, 1), (1, 0), (1, 0.4)):
        for name, value in (("Mode", mode), ("Thickness", thickness)):
            subtype = ("DISTANCE" if mode else "NONE") if name == "Thickness" else None
            set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, name, subtype=subtype), value)
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        result = evaluated.to_mesh()
        try:
            y = np.array([vertex.co.y for vertex in result.vertices])
            assert np.isfinite(y).all() and len(y)
            if thickness == 0:
                assert len(result.polygons) == 4 and np.max(abs(y)) < 1e-7
                assert all(abs(item.value) < 1e-7 for item in result.attributes["o_normal_reduction"].data)
            else:
                back, front = (-0.6, 0.6) if mode == 0 else (0.0, thickness)
                assert np.isclose(y.min(), back) and np.isclose(y.max(), front)
                uses = Counter(tuple(sorted((a,b))) for face in result.polygons for a,b in zip(face.vertices, (*face.vertices[1:],face.vertices[0])))
                assert set(uses.values()) == {2}
        finally:
            evaluated.to_mesh_clear()
