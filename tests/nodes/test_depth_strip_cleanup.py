"""Evaluate opposite-boundary cleanup on explicit mesh topology."""

import bmesh
import bpy
import numpy as np
import pytest

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
