import bpy
import numpy as np
import pytest
from tests.support.planes import surface


def test_conversion_preserves_offset_world_placement_and_initializes_inputs(surface, monkeypatch):
    from anyimage.operators.convert_to_plane import object as conversion
    from anyimage.common.image import image_empty_bounds
    from anyimage.common.depth import reference_depth
    from mathutils import Matrix, Vector

    obj, _, _, inputs, image = surface
    group = obj.modifiers[0].node_group
    monkeypatch.setattr(conversion, "load_node_group", lambda name: group)
    source = bpy.data.objects.new("Offset Image", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 4
    source.empty_image_offset = (-0.2, -0.8)
    source.matrix_world = Matrix.Translation((3, -2, 5)) @ Matrix.Rotation(0.7, 4, "Y") @ Matrix.Diagonal((2, 3, 1, 1))
    bpy.context.collection.objects.link(source)
    bounds = image_empty_bounds(source)
    matrix = source.matrix_world.copy()
    material = bpy.data.materials.new("Conversion")
    metadata = {"image_size": (16, 8),
                "intrinsics": ((4, 0, 5), (0, 4, 3), (0, 0, 1))}
    result = conversion.create_depth_plane_object(
        bpy.context, source, 2, material, image, metadata, "DEPTH")
    assert result.name == "Offset Image"
    assert result["anyimage_mesh_shape"] == "DEPTH_PLANE"
    assert bpy.context.view_layer.objects.active == result
    expected = sorted(tuple(matrix @ Vector((x, y, 0)))
                      for x in bounds[:2] for y in bounds[2:])
    actual = sorted(tuple(result.matrix_world @ v.co) for v in result.data.vertices)
    np.testing.assert_allclose(actual, expected, atol=1e-6)
    center = matrix @ Vector(((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, 0))
    np.testing.assert_allclose(result.matrix_world.translation, center, atol=1e-6)
    modifier = result.modifiers[0]
    assert modifier[inputs["Thickness"].identifier] == 0
    assert modifier[inputs["Depth Image"].identifier] == image
    assert modifier[inputs["Depth Mask"].identifier] is True
    assert modifier[inputs["Reference Depth"].identifier] == pytest.approx(
        reference_depth(image) * modifier[inputs["Uniform Scale"].identifier])
    assert result.data.materials[0] == material


def test_failed_modifier_initialization_removes_partial_object(surface, monkeypatch):
    from anyimage.operators.convert_to_plane import object as conversion

    obj, _, _, _, image = surface
    monkeypatch.setattr(conversion, "load_node_group", lambda name: obj.modifiers[0].node_group)
    source = bpy.data.objects.new("Source", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    bpy.context.collection.objects.link(source)
    material = bpy.data.materials.new("Unused")
    before_objects, before_meshes = set(bpy.data.objects), set(bpy.data.meshes)

    def fail(*args):
        raise RuntimeError("input failed")

    monkeypatch.setattr(conversion, "set_modifier_input", fail)
    metadata = {"image_size": (16, 8),
                "intrinsics": ((4, 0, 5), (0, 4, 3), (0, 0, 1))}
    with pytest.raises(RuntimeError, match="input failed"):
        conversion.create_depth_plane_object(bpy.context, source, 2, material, image, metadata, "DEPTH")
    assert set(bpy.data.objects) == before_objects
    assert set(bpy.data.meshes) == before_meshes
    assert material.users == 0
