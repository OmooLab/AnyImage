"""Behavior checks for face separation and connected Depth Surface shells."""

import bpy
import bmesh
import numpy as np
import pytest


from tests.support.depth_surface import evaluated, surface


@pytest.mark.parametrize("size", [0.01, 100.0])
def test_split_mapping_and_uniform_scale(size):
    obj, set_value = surface(step=2.0, size=size)
    # The normalized ray jump crosses the threshold only at full strength.
    counts = []
    for split in (0.0, 0.25, 0.5, 1.0):
        set_value("Depth Split", split)
        coords, faces = evaluated(obj)
        counts.append(len(coords))
        assert len(faces) == 8
    assert counts[:3] == [15] * 3
    assert counts[3] == 18
    set_value("Depth Scale", 0.0)
    coords, _ = evaluated(obj)
    assert len(coords) == counts[0] and np.abs(coords[:, 1]).max() < 1e-6


def test_midpoint_selects_relative_ray_jump_and_preserves_faces():
    obj, set_value = surface(step=4.0)
    set_value("Depth Split", 0.5)
    coords, faces = evaluated(obj)
    assert len(coords) == 18 and len(faces) == 8
    assert set(np.round(coords[:, 1], 4)) == {2.0, -2.0}


@pytest.mark.parametrize("depth_scale", [0.0, 1.0])
def test_depth_scale_scales_split_selection(depth_scale):
    obj, set_value = surface(step=4.0)
    set_value("Depth Scale", depth_scale)
    set_value("Depth Split", 0.0)
    whole, whole_faces = evaluated(obj)
    set_value("Depth Split", 0.5)
    coords, faces = evaluated(obj)
    assert np.isfinite(coords).all()
    if depth_scale == 0.0:
        # A flat projection keeps every face, so there is nothing to separate.
        np.testing.assert_allclose(coords, whole, atol=1e-6)
        assert faces == whole_faces
    else:
        assert len(coords) > len(whole)


def test_depth_scale_multiplies_split_strength():
    obj, set_value = surface(step=4.0)
    set_value("Depth Scale", 0.5)
    set_value("Depth Split", 1.0)
    scaled, scaled_faces = evaluated(obj)
    set_value("Depth Scale", 1.0)
    set_value("Depth Split", 0.5)
    reference, reference_faces = evaluated(obj)
    assert len(scaled) == len(reference) > 15
    assert scaled_faces == reference_faces


@pytest.mark.parametrize("resolution", [1, 4])
def test_planar_depth_preserves_blocks_and_cleans_single_face_width(resolution):
    obj, set_value = surface(step=0.0, resolution=resolution)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    original, original_faces = evaluated(obj)
    set_value("Depth Split", 1.0)
    coords, faces = evaluated(obj)
    if resolution == 1:
        assert len(coords) == 0 and not faces
        return
    assert len(faces) == len(original_faces)
    assert np.isfinite(coords).all()


def test_outline_points_use_adjacent_face_depth_without_split():
    obj, set_value = surface(step=0.0, resolution=2)
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], np.float32).reshape(32, 64, 4)
    pixels[..., 2] = 1
    # Spike both edge rows to cover Blender's image origin without relying on it.
    pixels[(0, -1), :, 2] = 10
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    set_value("Depth Split", 0.0)
    coords, faces = evaluated(obj)
    boundary = np.isclose(coords[:, 2], 0, atol=0.05) | np.isclose(coords[:, 2], 1, atol=0.05)
    assert boundary.any()
    np.testing.assert_allclose(coords[boundary, 1], 0, atol=1e-5)


def test_small_positive_split_preserves_unsplit_projection():
    obj, set_value = surface(step=2.0)
    original, original_faces = evaluated(obj)
    set_value("Depth Split", 0.01)
    coords, faces = evaluated(obj)
    np.testing.assert_allclose(coords, original, atol=1e-6)
    assert faces == original_faces


def test_cut_vertices_preserve_camera_rays_and_other_vertices():
    obj, set_value = surface(step=4.0)
    original, original_faces = evaluated(obj)
    set_value("Depth Split", 0.5)
    coords, faces = evaluated(obj)
    for source_face, result_face in zip(original_faces, faces):
        for source_index, result_index in zip(source_face, result_face):
            before, after = original[source_index], coords[result_index]
            if obj.data.vertices[source_index].co.x != 1.0:
                np.testing.assert_allclose(after, before, atol=1e-6)
            else:
                assert not np.allclose(after, before, atol=1e-6)


@pytest.mark.parametrize("thickness", [0.0, 0.2])
def test_temporary_fields_are_removed_and_user_attributes_survive(thickness):
    obj, set_value = surface()
    obj.data.attributes.new("o_depth_probe", "FLOAT", "POINT")
    attribute = obj.data.attributes.new("o_user_weight", "FLOAT", "POINT")
    obj.data.attributes.new(".o_user_weight", "FLOAT", "POINT")
    for value in attribute.data:
        value.value = 0.75
    set_value("Depth Split", 0.5)
    set_value("Thickness", thickness)
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        assert {a.name for a in mesh.attributes if a.name.startswith(("o_depth_", "o_balloon_surface_"))} == {"o_depth_probe"}
        assert "UVMap" in mesh.attributes
        assert ".o_user_weight" in mesh.attributes
        assert not any("o_anyimage" in a.name for a in mesh.attributes)
        assert not any(a.name.startswith("_o_") for a in mesh.attributes)
        assert all(
            v.value == pytest.approx(0.75)
            for v in mesh.attributes["o_user_weight"].data
        )
    finally:
        result.to_mesh_clear()


def output_split_mesh(obj):
    """Inspect separation before boundary strip cleanup."""
    group = obj.modifiers[0].node_group
    split = next(node for node in group.nodes if node.bl_idname == "GeometryNodeSplitEdges")
    output = next(node for node in group.nodes if node.bl_idname == "NodeGroupOutput")
    group.links.new(split.outputs["Mesh"], output.inputs["Geometry"])


def test_zero_center_distance_does_not_split_or_produce_nan():
    obj, set_value = surface(step=6.0)
    output_split_mesh(obj)
    mesh = bpy.data.meshes.new("Coincident face centers")
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (0.5, 1, 0), (0.5, 1, 0)], [], [(0, 1, 2), (1, 0, 3)]
    )
    uv = mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        for li in face.loop_indices:
            uv.data[li].uv = (0.25 if face.index == 0 else 0.75, 0.5)
    obj.data = mesh
    set_value("Depth Split", 1.0)
    coords, faces = evaluated(obj)
    assert len(coords) == 4 and len(faces) == 2
    assert np.isfinite(coords).all()


@pytest.mark.parametrize("resolution", [1, 4])
def test_relative_distance_slope_has_density_independent_selection(resolution):
    obj, set_value = surface(step=0.0, resolution=resolution)
    output_split_mesh(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], np.float32).reshape(32, 64, 4)
    pixels[..., 2] = np.exp(6 * pixels[..., 0])
    pixels[..., :2] = 0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Split", 0.25)
    assert len(evaluated(obj)[0]) == len(obj.data.vertices)
    set_value("Depth Split", 1.0)
    assert len(evaluated(obj)[0]) > len(obj.data.vertices)

@pytest.mark.parametrize("kind", ["plane", "cutout"])
def test_split_uses_ray_distance_and_ignores_absolute_distance_scale(kind):
    from tests.support.planes import create_surface

    if kind == "plane":
        obj, set_value, _, _, image = create_surface("DEPTH")
        set_value("Subdivide", 1)
        set_value("Depth Scale", 1)
    else:
        obj, set_value = surface(step=0)
        image = bpy.data.images["Camera"]
    output_split_mesh(obj)
    set_value("Reference Depth", 3)
    set_value("Depth Split", 0)
    width, height = image.size
    pixels = np.ones((height, width, 4), np.float32)
    original_count = len(evaluated(obj)[0])
    set_value("Depth Split", 1)
    # Equal axial Z, but a tenfold ray-distance jump: Z-only splitting misses it.
    pixels[..., :3] = (0, 0, 1)
    pixels[:, width // 2:, 0] = np.sqrt(99)
    signature = None
    for scale in (0.01, 1.0, 100.0):
        scaled = pixels.copy()
        scaled[..., :3] *= scale
        image.pixels.foreach_set(scaled.ravel())
        image.update()
        set_value("Depth Image", image)
        points, faces = evaluated(obj)
        assert len(points) > original_count
        if signature is None:
            signature = points, faces
        np.testing.assert_array_equal(points, signature[0])
        assert faces == signature[1]
    # Equal ray distances with different Z must keep the faces connected.
    pixels[..., :3] = (0, 0, 10)
    pixels[:, width // 2:, :3] = (8, 0, 6)
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Depth Image", image)
    assert len(evaluated(obj)[0]) == original_count
    # Degenerate distances and a zero reference remain finite and connected.
    pixels[..., :3] = 0
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value("Reference Depth", 0)
    points, _ = evaluated(obj)
    assert len(points) == original_count and np.isfinite(points).all()
