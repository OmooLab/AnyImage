from unittest.mock import patch
import bpy
import numpy as np
from mathutils import Matrix, Vector


from anyimage.common import image as image_data
from anyimage.common import object as object_data
from anyimage.common.coordinate import canonical_direction_to_legacy
from anyimage.operators.clipboard_image import actions as clipboard_actions
from anyimage.operators.convert_to_plane import object as plane_object
from anyimage.operators.cutout_tool import shape as cutout_shape
from tests.support.image_objects import _depth_image, _depth_metadata, _evaluated_positions, _inputs
from nodes.groups.image_plane import build_image_plane_group
from nodes.groups.image_depth_plane import build_image_depth_plane_group
from nodes.groups.image_relief_plane import build_image_relief_plane_group


def test_build_plane_keeps_one_quad_and_generates_topology_in_geometry_nodes():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Source", width=4096, height=2048)
    source = bpy.data.objects.new("Source", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    material = bpy.data.materials.new("Source.material")

    result = plane_object.create_plane_object(
        bpy.context,
        source,
        2,
        material,
    )

    assert result["anyimage_mesh_shape"] == "PLANE"
    assert len(result.data.vertices) == 4
    assert len(result.data.polygons) == 1
    assert all(polygon.use_smooth for polygon in result.data.polygons)
    assert cutout_shape.BALLOON_ATTRIBUTE_NAME not in result.data.attributes
    assert result.modifiers[0].node_group.name == "O Image Plane"
    evaluated = result.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_mesh = evaluated.to_mesh()
    try:
        assert len(evaluated_mesh.polygons) > 0
        assert result.data.materials[0] == material
        assert evaluated_mesh.materials[0].original == material
        assert all(polygon.material_index == 0 for polygon in evaluated_mesh.polygons)
    finally:
        evaluated.to_mesh_clear()


def test_clipboard_plane_uses_the_mesh_material_slot():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Clipboard Plane", width=128, height=64, alpha=True)

    with patch.object(clipboard_actions, "_place_in_view"):
        result = clipboard_actions.add_image_plane(bpy.context, image)

    assert _inputs(result.modifiers[0].node_group) == [
        "Geometry",
        "Subdivide",
        "Thickness",
    ]
    assert len(result.data.materials) == 1
    evaluated = result.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_mesh = evaluated.to_mesh()
    try:
        assert evaluated_mesh.materials[0].original == result.data.materials[0]
        assert all(polygon.material_index == 0 for polygon in evaluated_mesh.polygons)
    finally:
        evaluated.to_mesh_clear()


def test_converted_planes_center_the_origin_without_moving_world_corners():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    saved = build_image_depth_plane_group(build_image_plane_group())

    def create_source(name):
        image = bpy.data.images.new(name, width=200, height=100)
        source = bpy.data.objects.new(name, None)
        source.empty_display_type = "IMAGE"
        source.data = image
        source.empty_display_size = 2.0
        source.empty_image_offset = (0.25, -0.2)
        source.matrix_world = (
            Matrix.Translation((3.0, -2.0, 5.0))
            @ Matrix.Rotation(0.4, 4, "Z")
            @ Matrix.Diagonal((1.5, 0.75, 2.0, 1.0))
        )
        bpy.context.collection.objects.link(source)
        return source

    def assert_centered(result, bounds, source_matrix):
        x_min, x_max, y_min, y_max = bounds
        center = Vector(
            ((x_min + x_max) * 0.5, (y_min + y_max) * 0.5, 0.0)
        )
        assert np.allclose(
            tuple(result.matrix_world.translation),
            tuple(source_matrix @ center),
            atol=1e-6,
        )
        local = np.asarray([tuple(vertex.co) for vertex in result.data.vertices])
        assert np.allclose(local[:, [0, 2]].min(axis=0), (-1.0, -0.5), atol=1e-6)
        assert np.allclose(local[:, [0, 2]].max(axis=0), (1.0, 0.5), atol=1e-6)
        expected = sorted(
            tuple(source_matrix @ Vector((x, y, 0.0)))
            for x in (x_min, x_max)
            for y in (y_min, y_max)
        )
        actual = sorted(
            tuple(result.matrix_world @ vertex.co)
            for vertex in result.data.vertices
        )
        assert np.allclose(actual, expected, atol=1e-6)

    plane_source = create_source("Centered Plane")
    plane_bounds = image_data.image_empty_bounds(plane_source)
    plane_matrix = plane_source.matrix_world.copy()
    plane_material = bpy.data.materials.new("Centered Plane Material")
    plane = plane_object.create_plane_object(
        bpy.context,
        plane_source,
        0,
        plane_material,
    )
    assert_centered(plane, plane_bounds, plane_matrix)
    assert plane["anyimage_mesh_shape"] == "PLANE"

    depth_source = create_source("Centered Depth Plane")
    depth_bounds = image_data.image_empty_bounds(depth_source)
    depth_matrix = depth_source.matrix_world.copy()
    depth_values = np.ones((2, 2, 3), dtype=np.float32)
    depth_image = _depth_image(depth_values, np.ones((2, 2), dtype=bool))
    depth_material = bpy.data.materials.new("Centered Depth Material")
    depth_plane = plane_object.create_depth_plane_object(
        bpy.context,
        depth_source,
        0,
        depth_material,
        depth_image,
        _depth_metadata(
            ((0.5, 0.0, 0.5), (0.0, 0.5, 0.5), (0.0, 0.0, 1.0)),
            (2, 2),
        ),
        "DEPTH",
    )
    assert_centered(depth_plane, depth_bounds, depth_matrix)
    assert depth_plane["anyimage_mesh_shape"] == "DEPTH_PLANE"
    depth_modifier = depth_plane.modifiers[0]
    assert depth_modifier.node_group == saved
    assert saved.name == "O Image Depth Plane"
    uniform_scale = depth_modifier[
        object_data.modifier_input_identifier(
            depth_modifier.node_group,
            "Uniform Scale",
        )
    ]
    assert np.isclose(
        depth_modifier[
            object_data.modifier_input_identifier(
                depth_modifier.node_group,
                "Reference Depth",
            )
        ],
        uniform_scale,
    )


def test_relief_plane_builds_a_fixed_base_terrain_block():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_image_relief_plane_group(build_image_plane_group())
    image = bpy.data.images.new("Terrain", width=4, height=4)
    source = bpy.data.objects.new("Terrain", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    material = bpy.data.materials.new("Terrain Material")
    depth_image = _depth_image(
        np.ones((4, 4, 3), dtype=np.float32),
        np.ones((4, 4), dtype=bool),
    )
    result = plane_object.create_depth_plane_object(
        bpy.context,
        source,
        2,
        material,
        depth_image,
        _depth_metadata(
            ((1.5, 0.0, 1.5), (0.0, 1.5, 1.5), (0.0, 0.0, 1.0)),
            (4, 4),
        ),
        "RELIEF",
    )
    assert result["anyimage_mesh_shape"] == "RELIEF_PLANE"
    assert result.modifiers[0].node_group.name == "O Image Relief Plane"
    modifier = result.modifiers[0]
    group = modifier.node_group
    assert modifier[
        object_data.modifier_input_identifier(group, "Thickness")
    ] == 0.0
    assert modifier[
        object_data.modifier_input_identifier(group, "Depth Scale")
    ] == 0.5
    assert modifier[
        object_data.modifier_input_identifier(group, "Depth Offset")
    ] == 0.0

    def set_input(name, value):
        object_data.set_modifier_input(
            modifier,
            object_data.modifier_input_identifier(group, name),
            value,
        )
        result.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()

    set_input("Depth Scale", 0.0)
    set_input("Thickness", 0.1)
    set_input("Depth Offset", 0.0)
    baseline = _evaluated_positions(result)
    assert np.isclose(baseline[:, 1].min(), 0.0, atol=1e-6)
    assert np.isclose(baseline[:, 1].max(), 0.1, atol=1e-6)
    baseline_base = {
        (round(float(x), 6), round(float(y), 6))
        for x, y, z in baseline
        if np.isclose(y, 0.0, atol=1e-6)
    }

    evaluated = result.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_mesh = evaluated.to_mesh()
    try:
        assert result.data.materials[0] == material
        assert evaluated_mesh.materials[0].original == material
        assert all(polygon.material_index == 0 for polygon in evaluated_mesh.polygons)
        assert "UVMap" in evaluated_mesh.uv_layers
    finally:
        evaluated.to_mesh_clear()

    set_input("Depth Scale", 1.0)
    set_input("Reference Depth", 1.2)
    outward = _evaluated_positions(result)
    assert np.isclose(outward[:, 1].min(), -0.2, atol=1e-6)
    assert np.isclose(outward[:, 1].max(), 0.1, atol=1e-5)
    outward_base = {
        (round(float(x), 6), round(float(y), 6))
        for x, y, z in outward
        if np.isclose(y, 0.0, atol=1e-6)
    }
    assert outward_base == baseline_base
    y_levels = np.unique(np.round(outward[:, 1], 6))
    assert len(y_levels) >= 4
    assert np.allclose(np.diff(y_levels), np.diff(y_levels)[0], atol=1e-5)

    set_input("Reference Depth", 0.95)
    inward = _evaluated_positions(result)
    assert np.isclose(inward[:, 1].min(), 0.0, atol=1e-6)
    assert np.isclose(inward[:, 1].max(), 0.1, atol=1e-5)

    set_input("Reference Depth", 0.0)
    limited = _evaluated_positions(result)
    assert np.isclose(limited[:, 1].min(), 0.0, atol=1e-6)
    assert np.isclose(limited[:, 1].max(), 0.1, atol=1e-5)

    set_input("Reference Depth", 1.3)
    outward_beyond_thickness = _evaluated_positions(result)
    assert np.isclose(outward_beyond_thickness[:, 1].max(), 0.1, atol=1e-5)

    set_input("Thickness", 0.0)
    set_input("Reference Depth", 1.2)
    sheet = _evaluated_positions(result)
    assert np.isfinite(sheet).all()
    set_input("Reference Depth", 0.8)
    assert np.allclose(_evaluated_positions(result)[:, 1], 0.0, atol=1e-5)


def test_relief_plane_initializes_a_fitted_depth_direction():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_image_relief_plane_group(build_image_plane_group())
    image = bpy.data.images.new("Sloped Relief", width=5, height=3)
    source = bpy.data.objects.new("Sloped Relief", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    bounds = image_data.image_empty_bounds(source)
    x = bounds[0] + (np.arange(5) + 0.5) / 5 * (bounds[1] - bounds[0])
    y = bounds[3] - (np.arange(3) + 0.5) / 3 * (bounds[3] - bounds[2])
    xx, yy = np.meshgrid(x, y)
    depth = 2.0 + 0.2 * xx + 0.1 * yy
    depth_image = _depth_image(
        np.repeat(depth[..., None], 3, axis=2),
        np.ones(depth.shape, dtype=bool),
    )
    metadata = _depth_metadata(
        ((2.0, 0.0, 2.0), (0.0, 2.0, 1.0), (0.0, 0.0, 1.0)),
        (5, 3),
    )
    result = plane_object.create_depth_plane_object(
        bpy.context,
        source,
        2,
        bpy.data.materials.new("Sloped Relief Material"),
        depth_image,
        metadata,
        "RELIEF",
    )
    modifier = result.modifiers[0]
    direction = modifier[
        object_data.modifier_input_identifier(modifier.node_group, "Depth Direction")
    ]
    uniform_scale = modifier[
        object_data.modifier_input_identifier(modifier.node_group, "Uniform Scale")
    ]
    canonical = np.asarray((0.2 * uniform_scale, 1.0, -0.1 * uniform_scale))
    expected = np.asarray(canonical_direction_to_legacy(canonical))
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(direction, expected, atol=1e-6)
