"""Check temporary attribute lifetimes across depth modifier branches."""

import bpy
import pytest

from tests.support.depth_surface import surface
from tests.support.planes import create_surface
from tests.nodes.test_image_depth_panorama import panorama


@pytest.mark.parametrize("kind", ["cutout", "plane", "panorama"])
def test_depth_attribute_cleanup_has_no_warnings(kind):
    if kind == "cutout":
        obj, set_value = surface()
    elif kind == "plane":
        obj, set_value, *_ = create_surface("DEPTH")
        set_value("Depth Scale", 1)
    else:
        obj, set_value = panorama(subdivide=2)
    modifier = obj.modifiers[0]
    for split in (0.0, 0.5, 0.0):
        set_value("Depth Split", split)
        for smooth in (0, 5):
            set_value("Boundary Smooth", smooth)
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                assert mesh.vertices
                assert not any("o_anyimage" in a.name for a in mesh.attributes)
                assert not any(a.name.startswith("_o_") for a in mesh.attributes)
                assert not list(modifier.node_warnings), [
                    warning.message for warning in modifier.node_warnings
                ]
            finally:
                evaluated.to_mesh_clear()
