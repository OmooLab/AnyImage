from unittest.mock import patch
import bpy
import numpy as np
import pytest
from mathutils import Vector


from anyimage.common import depth as depth_data
from tests.support.color_image import color_image as prepared_color_image
from anyimage.common import image as image_data
from anyimage.common import material as material_data
from anyimage.common import object as object_data
from anyimage.common.selection import ImageEditWarning, SelectionPath, rasterize_selection_path
from anyimage.operators.cutout_tool import geometry as cutout_geometry
from anyimage.operators.cutout_tool import operators as cutout_main
from anyimage.operators.cutout_tool import shape as cutout_shape
from anyimage.operators.cutout_tool.boundary_padding import (
    image_rgba_buffer,
    pad_cutout_images,
)
from anyimage.server.geometry.depth_texture import (
    write_depth_texture,
)
from anyimage.server.models.geometry import GeometryFrame
from tests.support.image_objects import _create_cutout_shape, _depth_image, _depth_metadata, _evaluated_positions, _group_node


def test_depth_result_image_loads_camera_exr_and_keeps_data_name(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Source.png", width=2, height=2)
    source = bpy.data.objects.new("Source", None)
    source.data = source_image
    points = np.arange(12, dtype=np.float32).reshape((2, 2, 3))
    validity = np.asarray(((1.0, 0.0), (0.5, 1.0)), dtype=np.float32)
    frame = GeometryFrame(
        depth=points[..., 2].copy(),
        validity=validity,
        intrinsics=np.eye(3, dtype=np.float32),
        points=points,
    )
    path = tmp_path / "depth.exr"
    alpha = np.asarray(((0.8, 1.0), (0.75, 0.0)), dtype=np.float32)
    write_depth_texture(frame, path, alpha=alpha)
    metadata = _depth_metadata(np.eye(3), (2, 2))

    image = depth_data.load_depth_result_image(path, source, metadata)

    packed = np.empty(16, dtype=np.float32)
    image.pixels.foreach_get(packed)
    packed = np.flipud(packed.reshape((2, 2, 4)))
    assert np.array_equal(packed[..., :3], points)
    assert np.array_equal(packed[..., 3], alpha * validity)
    camera_depth, valid = depth_data.camera_depth_values(image)
    np.testing.assert_array_equal(camera_depth, points[..., 2])
    np.testing.assert_array_equal(
        valid,
        alpha * validity > depth_data.DEPTH_ALPHA_THRESHOLD,
    )
    assert image.alpha_mode == "CHANNEL_PACKED"
    assert image.name == "Source_depth.exr"


def test_depth_texture_keeps_points_outside_positive_validity(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Source.png", width=2, height=1)
    source = bpy.data.objects.new("Source", None)
    source.data = source_image
    frame = GeometryFrame(
        depth=np.asarray(((2.0, 7.0),), dtype=np.float32),
        points=np.asarray((((-1.0, 3.0, 2.0), (4.0, -2.0, 7.0)),), dtype=np.float32),
        validity=np.asarray(((1.0, 0.0),), dtype=np.float32),
        intrinsics=np.eye(3, dtype=np.float32),
    )
    path = tmp_path / "depth.exr"
    write_depth_texture(frame, path, alpha=np.ones_like(frame.validity))

    image = depth_data.load_depth_result_image(
        path,
        source,
        _depth_metadata(np.eye(3), (2, 1)),
    )

    packed = np.empty(8, dtype=np.float32)
    image.pixels.foreach_get(packed)
    packed = packed.reshape((1, 2, 4))
    assert np.array_equal(packed[..., :3], frame.points)
    assert np.array_equal(packed[..., 3], frame.validity)


def test_balloon_build_starts_from_the_unified_single_sheet():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Balloon Sheet", width=64, height=64, alpha=True)
    source = bpy.data.objects.new("Balloon Sheet", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    result = _create_cutout_shape(
        source,
        "SOLID",
        0.1,
    )

    assert all(abs(vertex.co.y) < 1e-8 for vertex in result.data.vertices)
    assert len(result.data.vertices) > 4
    assert len(result.data.polygons) > 1
    assert cutout_shape.BALLOON_ATTRIBUTE_NAME in result.data.attributes
    profile_attribute = result.data.attributes[cutout_shape.BALLOON_ATTRIBUTE_NAME]
    assert profile_attribute.data_type == "FLOAT"
    assert profile_attribute.domain == "POINT"
    profile = np.empty(len(result.data.vertices), dtype=np.float32)
    profile_attribute.data.foreach_get("value", profile)
    assert profile.min() == 0.0 and profile.max() > 0.0
    material_tree = result.data.materials[0].node_tree
    assert not any(node.bl_idname == "ShaderNodeAttribute" for node in material_tree.nodes)
    image_layer = _group_node(material_data.material_node_group(), material_tree)
    assert not image_layer.inputs["Normal Scale"].is_linked
    assert image_layer.inputs["Normal Scale"].default_value == 1.0
    assert result.modifiers[0].node_group.name == cutout_shape.CUTOUT_NODE_GROUP_NAMES["SOLID"]
    inward = result.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))
    assert np.allclose(tuple(inward), (0.0, 0.0, -1.0), atol=1e-6)


@pytest.mark.parametrize("gesture", ("LASSO", "POLYLINE"))
def test_depth_surface_object_evaluates(gesture):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Surface", width=64, height=64)
    source = bpy.data.objects.new("Surface", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    size = 8
    depth = np.ones((size, size), dtype=np.float32)
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    intrinsics = np.asarray(
        ((8.0, 0.0, 3.5), (0.0, 8.0, 3.5), (0.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    points = np.empty((size, size, 3), dtype=np.float32)
    points[..., 0] = (x - intrinsics[0, 2]) / intrinsics[0, 0] * depth
    points[..., 1] = (y - intrinsics[1, 2]) / intrinsics[1, 1] * depth
    points[..., 2] = depth
    valid = np.ones((size, size), dtype=bool)
    depth_image = _depth_image(points, valid)
    depth_metadata = _depth_metadata(intrinsics, (size, size))

    result = _create_cutout_shape(
        source,
        "DEPTH_SOLID",
        0.25,
        depth_image=depth_image,
        depth_metadata=depth_metadata,
        gesture=gesture,
    )

    assert all(abs(vertex.co.y) < 1e-8 for vertex in result.data.vertices)
    assert cutout_shape.BALLOON_ATTRIBUTE_NAME in result.data.attributes
    modifier = result.modifiers[0]
    assert modifier.node_group.name == cutout_shape.CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"]
    layer = _group_node(material_data.material_node_group(), result.data.materials[0].node_tree)
    assert layer.inputs["Object Space"].default_value is True
    assert modifier_value(modifier, object_data.modifier_input_identifier(modifier.node_group, "Mode")) == (1 if gesture == "POLYLINE" else 0)
    assert modifier_value(modifier, object_data.modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE")) == pytest.approx(0.2)
    assert modifier_value(modifier, object_data.modifier_input_identifier(modifier.node_group, "Thickness", subtype="NONE")) == 1.0
    object_data.set_modifier_input(
        modifier,
        object_data.modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"),
        0.0,
    )
    for name, value in (("Mode", 1), ("Front Inflation", 0.0)):
        object_data.set_modifier_input(modifier, object_data.modifier_input_identifier(modifier.node_group, name), value)
    scale_id = object_data.modifier_input_identifier(
        modifier.node_group,
        "Uniform Scale",
    )
    reference_id = object_data.modifier_input_identifier(
        modifier.node_group,
        "Reference Depth",
    )
    # The Depth texture holds a constant unit camera depth.
    assert modifier_value(modifier, reference_id) == pytest.approx(
        modifier_value(modifier, scale_id)
    )
    object_data.set_modifier_input(
        modifier,
        object_data.modifier_input_identifier(modifier.node_group, "Boundary Smooth"),
        0,
    )
    evaluated = result.evaluated_get(bpy.context.evaluated_depsgraph_get())
    baseline_mesh = evaluated.to_mesh()
    try:
        baseline_y = np.asarray([vertex.co.y for vertex in baseline_mesh.vertices])
        baseline_min = baseline_y.min()
        baseline_max = baseline_y.max()
    finally:
        evaluated.to_mesh_clear()

    object_data.set_modifier_input(
        modifier,
        object_data.modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"),
        1.0,
    )
    result.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    evaluated = result.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_mesh = evaluated.to_mesh()
    try:
        assert len(evaluated_mesh.polygons) > 0
        y = np.asarray([vertex.co.y for vertex in evaluated_mesh.vertices])
        assert np.isclose(y.min(), baseline_min, atol=1e-5)
        assert np.isclose(y.max(), baseline_max + 1.0, atol=1e-5)
    finally:
        evaluated.to_mesh_clear()

def test_depth_surface_keeps_continuous_points_across_zero_validity_edge():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Surface", width=64, height=64)
    source = bpy.data.objects.new("Surface", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    size = 8
    depth = np.ones((size, size), dtype=np.float32)
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    intrinsics = np.asarray(
        ((8.0, 0.0, 3.5), (0.0, 8.0, 3.5), (0.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    points = np.empty((size, size, 3), dtype=np.float32)
    points[..., 0] = (x - intrinsics[0, 2]) / intrinsics[0, 0] * depth
    points[..., 1] = (y - intrinsics[1, 2]) / intrinsics[1, 1] * depth
    points[..., 2] = depth
    validity = np.ones((size, size), dtype=bool)
    validity[[0, -1], :] = False
    validity[:, [0, -1]] = False

    result = _create_cutout_shape(
        source,
        "DEPTH_SOLID",
        0.1,
        depth_image=_depth_image(points, validity),
        depth_metadata=_depth_metadata(intrinsics, (size, size)),
    )
    modifier = result.modifiers[0]
    object_data.set_modifier_input(
        modifier,
        object_data.modifier_input_identifier(modifier.node_group, "Thickness"),
        0.0,
    )
    result.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    positions = _evaluated_positions(result)

    assert np.isfinite(positions).all()
    assert np.ptp(positions[:, 0]) > 1.5
    assert np.ptp(positions[:, 2]) > 1.5
    assert np.ptp(positions[:, 1]) < 1e-4


@pytest.mark.parametrize("gesture", ("LASSO", "POLYLINE"))
def test_depth_symmetry_uses_metric_plane_inputs(gesture):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Depth Symmetry", width=100, height=100, alpha=True)
    source = bpy.data.objects.new("Depth Symmetry", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    source.empty_display_size = 2.0
    bpy.context.collection.objects.link(source)
    crop_bounds = (50, 20, 90, 80)
    local_bounds = cutout_geometry.crop_plane_bounds(
        source,
        crop_bounds,
        (100, 100),
    )
    y, x = np.indices((61, 41), dtype=np.float32)
    normalized_x = x / 40.0 * 2.0 - 1.0
    normalized_y = y / 60.0 * 2.0 - 1.0
    points = np.zeros((61, 41, 3), dtype=np.float32)
    points[..., 0] = normalized_x
    points[..., 1] = normalized_y
    points[..., 2] = 2.0 + normalized_x * 0.15 - normalized_y * 0.1
    points[27:34, 17:24, 2] -= 0.25
    intrinsics = np.asarray(
        ((50.0, 0.0, 20.0), (0.0, 50.0, 30.0), (0.0, 0.0, 1.0)),
        dtype=np.float32,
    )
    valid = np.ones((61, 41), dtype=bool)
    depth_image = _depth_image(points, valid)
    depth_metadata = _depth_metadata(intrinsics, (41, 61))

    selection_values = np.ones((60, 40), dtype=np.float32)
    selection_values[:, :2] = 0.0
    result = _create_cutout_shape(
        source,
        "DEPTH_SYMMETRY",
        0.1,
        depth_image=depth_image,
        depth_metadata=depth_metadata,
        bounds=crop_bounds,
        selection_values=selection_values,
        gesture=gesture,
    )

    assert all(abs(vertex.co.y) < 1e-8 for vertex in result.data.vertices)
    assert cutout_shape.BALLOON_ATTRIBUTE_NAME in result.data.attributes
    assert {obj.name for obj in bpy.context.scene.objects} == {
        source.name,
        result.name,
    }
    assert len(result.modifiers) == 2
    modifier, symmetry = result.modifiers
    assert modifier.node_group.name == "O Image Depth Cutout"
    assert symmetry.node_group.name == "O Image Cutout Symmetry"
    layer = _group_node(material_data.material_node_group(), result.data.materials[0].node_tree)
    assert layer.inputs["Object Space"].default_value is True
    assert not modifier.show_group_selector and not symmetry.show_group_selector

    def value(modifier, name, subtype=None):
        return modifier_value(modifier, object_data.modifier_input_identifier(
            modifier.node_group, name, subtype=subtype))

    assert value(modifier, "Mode") == (1 if gesture == "POLYLINE" else 0)
    for subtype in ("NONE", "DISTANCE"):
        assert value(modifier, "Thickness", subtype) == 0
    initialized = {"Mode", "Depth Scale", "Uniform Scale", "Reference Depth", "Depth Image"}
    for socket in modifier.node_group.interface.items_tree:
        if (socket.item_type == "SOCKET" and socket.in_out == "INPUT"
                and socket.name not in initialized
                and socket.socket_type in {"NodeSocketFloat", "NodeSocketInt"}):
            assert modifier_value(modifier, socket.identifier) == pytest.approx(socket.default_value)
    assert isinstance(value(modifier, "Depth Image"), bpy.types.Image)
    assert value(modifier, "Uniform Scale") > 0
    assert value(modifier, "Reference Depth") > 0
    assert not np.allclose(value(symmetry, "Direction"), (0, 1, 0))
    crop_center = Vector(((local_bounds[0] + local_bounds[1]) / 2,
                          (local_bounds[2] + local_bounds[3]) / 2, 0))
    np.testing.assert_allclose(result.matrix_world.translation, source.matrix_world @ crop_center, atol=1e-5)
    from scipy.spatial import cKDTree
    positions = _evaluated_positions(result)
    assert len(positions) and np.isfinite(positions).all()
    assert cKDTree(positions).query(positions * (-1, 1, 1))[0].max() < 1e-5
    # Both modes start from the same front, including after changing the menu.
    object_data.set_modifier_input(modifier,
        object_data.modifier_input_identifier(modifier.node_group, "Mode"),
        0 if gesture == "POLYLINE" else 1)
    result.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    changed = _evaluated_positions(result)
    np.testing.assert_array_equal(changed, positions)


@pytest.mark.parametrize("float_buffer", (False, True))
def test_boundary_padding_preserves_independent_blender_image_interpretation(float_buffer):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = bpy.data.images.new(
        "Padding Source", width=9, height=9, alpha=True, float_buffer=float_buffer
    )
    padded = bpy.data.images.new(
        "Padding Color", width=9, height=9, alpha=True, float_buffer=float_buffer
    )
    source.alpha_mode = padded.alpha_mode = "CHANNEL_PACKED"
    values = np.zeros((9, 9, 4), dtype=np.float32)
    values[2:7, 2:7] = (0.25, 0.5, 0.75, 1.0)
    source.pixels.foreach_set(np.flipud(values).ravel())
    padded.pixels.foreach_set(np.flipud(values).ravel())
    original = image_rgba_buffer(source)

    pad_cutout_images(padded, None, None, values[..., 3], 0.5, 2.0)

    np.testing.assert_array_equal(image_rgba_buffer(source), original)
    assert image_rgba_buffer(padded)[1, 4, 3] == pytest.approx(1.0)
    assert padded.is_float is float_buffer
    assert padded.alpha_mode == "CHANNEL_PACKED"
    assert padded.packed_file is not None


def test_local_cutout_selection_matches_uint8_tenth_alpha_boundary():
    top_down = np.ones((4, 4, 4), dtype=np.float32)
    top_down[1, 1, 3] = 25.0 / 255.0
    top_down[1, 2, 3] = 26.0 / 255.0
    selection_mask = rasterize_selection_path(
        (4, 4),
        SelectionPath(
            points=((0, 0), (4, 0), (4, 4), (0, 4)),
        ),
    )
    selection = cutout_main._cutout_content_values(
        top_down[:, :, 3],
        selection_mask.values,
    )

    assert selection[1, 1] <= cutout_geometry.CUTOUT_ALPHA_THRESHOLD
    assert selection[1, 2] > 0.1


def test_cutout_content_merge_keeps_the_geometric_selection_unchanged():
    selection = np.asarray(((0.25, 1.0), (0.5, 0.75)), dtype=np.float32)
    original = selection.copy()
    alpha = np.asarray(((1.0, 0.5), (0.0, 0.25)), dtype=np.float32)

    content = cutout_main._cutout_content_values(
        alpha, selection, alpha_threshold=0.5
    )

    np.testing.assert_array_equal(selection, original)
    np.testing.assert_allclose(content, alpha * original)
    with pytest.raises(ImageEditWarning, match="no visible image pixels"):
        cutout_main._cutout_content_values(np.zeros((2, 2)), selection)


def test_local_cutout_builds_from_blender_image_pixels_without_a_job():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Local Cutout", width=64, height=48, alpha=True)
    source_rgba = np.ones((48, 64, 4), dtype=np.float32)
    source_rgba[:, :, 3] = np.linspace(0.25, 1.0, 48, dtype=np.float32)[:, None]
    image.pixels.foreach_set(np.flipud(source_rgba).ravel())
    source = bpy.data.objects.new("Local Cutout", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    bpy.context.collection.objects.link(source)
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    selection_path = SelectionPath(
        points=((-8, 8), (72, 8), (72, 40), (-8, 40)),
    )
    source_bounds = image_data.image_empty_bounds(source)

    with patch.object(
        image_data,
        "image_rgba",
        wraps=image_data.image_rgba,
    ) as read_rgba:
        rgba = image_data.image_rgba(image)
        selection_mask = rasterize_selection_path(
            tuple(image.size),
            selection_path,
            antialias=True,
        )
        left, top, right, bottom = selection_mask.bounds
        content_values = cutout_main._cutout_content_values(
            rgba[top:bottom, left:right, 3],
            selection_mask.values,
            alpha_threshold=0.5,
        )
        color_image = prepared_color_image(
            source.data,
            selection_mask.bounds,
            rgba,
        )
        cutout_main.create_cutout_shape(
            bpy.context,
            source,
            "FLAT",
            0.1,
            content_values,
            selection_mask.bounds,
            alpha_threshold=0.5,
            boundary_padding=0.0,
            color_image=color_image,
        )

    read_rgba.assert_called_once_with(image)

    result = bpy.context.view_layer.objects.active
    assert result is not source
    assert result.type == "MESH"
    assert result["anyimage_mesh_shape"] == "FLAT"
    modifier = result.modifiers[0]
    assert modifier.node_group.name == cutout_shape.CUTOUT_NODE_GROUP_NAMES["FLAT"]
    assert len(result.data.vertices) > 4
    assert len(result.data.polygons) > 1
    assert all(polygon.use_smooth for polygon in result.data.polygons)
    assert all(abs(vertex.co.y) < 1e-8 for vertex in result.data.vertices)
    assert cutout_shape.BALLOON_ATTRIBUTE_NAME in result.data.attributes
    source_inverse = source.matrix_world.inverted()
    source_x = [
        (source_inverse @ (result.matrix_world @ vertex.co)).x
        for vertex in result.data.vertices
    ]
    assert min(source_x) >= source_bounds[0]
    assert max(source_x) <= source_bounds[1]
    assert bpy.data.objects.get(source.name) is source
    assert result.data.materials[0].node_tree is not None
    color_texture = next(
        node
        for node in result.data.materials[0].node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    assert color_texture.image is not image
    assert tuple(color_texture.image.size) == (64, 36)
    copied = np.empty(36 * 64 * 4, dtype=np.float32)
    color_texture.image.pixels.foreach_get(copied)
    copied = copied.reshape((36, 64, 4))
    assert np.allclose(copied[:, :, :3], 1.0)
    left, top, right, bottom = selection_mask.bounds
    assert np.allclose(
        copied[:, :, 3], np.flipud(rgba[top:bottom, left:right, 3])
    )


def modifier_value(modifier, identifier):
    """Read modifier values through the runtime's socket API."""
    inputs = object_data._modifier_input_slots(modifier)
    if inputs is None:
        return modifier[identifier]
    slot = getattr(inputs, identifier)
    prop = slot.bl_rna.properties["value"]
    if prop.type == "ENUM":
        return list(prop.enum_items.keys()).index(slot.value)
    return slot.value
