"""Build O Image Depth Cutout."""
import bpy
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import (
    interface_socket, group_input, float_input, boolean_node, read_float_attribute, read_vector_attribute,
    read_int_attribute, store_float_attribute, store_vector_attribute, store_int_attribute,
    store_boolean_attribute, remove_attribute_pattern, prepare_node_group, evaluate_field,
    compare_node, sample_field,
)
from ..common.boundary_smoothing import boundary_influence
from ..common.cutout import _position_field, _shade_output
from ..common.depth_surface import (
    _math, build_surface_camera, limit_depth_surface, project_depth_surface,
    sample_face_camera, split_depth_surface,
)
from ..common.smoothing import edge_boundary_field, pinned_smooth
from ..common.cutout_boundary import remove_boundary_triangles, taper_split_profile


NODE_GROUP_NAME = "O Image Depth Cutout"
FRONT_NORMAL_ATTRIBUTE = "_o_front_normal"
BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE = "_o_boundary_smooth_weight"
BOUNDARY_FALLOFF_ATTRIBUTE = "_o_boundary_falloff"
CUT_BOUNDARY_ATTRIBUTE = "_o_cut_boundary"
LEAF_ID_ATTRIBUTE = "_o_leaf_id"
LEAF_SOURCE_INDEX_ATTRIBUTE = "_o_leaf_source_index"
SIDE_RING_TARGET_ATTRIBUTE = "_o_side_ring_target"
SIDE_BASE_UV_ATTRIBUTE = "_o_side_base_uv"
SIDE_TOP_UV_ATTRIBUTE = "_o_side_top_uv"
BALLOON_THICKNESS_BASE = 1.0
NORMAL_SMOOTH_ITERATIONS = 128
BOUNDARY_NORMAL_BLEND = 0.25
SIDE_UV_BLUR_ITERATIONS = 4
SIDE_UV_INFLUENCE_ITERATIONS = 4
LEAF_UV_PULL = 0.5
THICKNESS_TRANSITION = 1.0
SIDE_RING_OFFSET_FACTOR = 0.125


def build_normal_weight(group, is_shell, profile):
    """Keep shell smoothing and let the balloon profile drive the blend."""
    weight = group.nodes.new("GeometryNodeSwitch")
    weight.input_type = "FLOAT"
    group.links.new(is_shell, weight.inputs["Switch"])
    group.links.new(profile, weight.inputs["False"])
    weight.inputs["True"].default_value = 0.0
    return weight.outputs[0]


def build_profile_weight(group, geometry):
    """Normalize the corrected balloon profile into a zero to one blend weight."""
    profile = read_float_attribute(group, "o_balloon")
    statistics = group.nodes.new("GeometryNodeAttributeStatistic")
    statistics.data_type, statistics.domain = "FLOAT", "POINT"
    group.links.new(geometry, statistics.inputs["Geometry"])
    group.links.new(profile, statistics.inputs["Attribute"])
    return _math(
        group, "DIVIDE", profile,
        _math(group, "MAXIMUM", statistics.outputs["Max"], 1e-6),
    )


def build_island_normal(group, normal):
    """Normalize the sum of point normals within each connected mesh island."""
    nodes, links = group.nodes, group.links
    island = nodes.new("GeometryNodeInputMeshIsland")
    accumulate = nodes.new("GeometryNodeAccumulateField")
    accumulate.data_type, accumulate.domain = "FLOAT_VECTOR", "POINT"
    links.new(normal, accumulate.inputs["Value"])
    links.new(island.outputs["Island Index"], accumulate.inputs["Group Index"])
    normalize = nodes.new("ShaderNodeVectorMath")
    normalize.operation = "NORMALIZE"
    links.new(accumulate.outputs["Total"], normalize.inputs[0])
    return normalize.outputs["Vector"]


def build_smoothed_normals(group):
    """Return blurred normals and an independent island average of raw normals."""
    nodes, links = group.nodes, group.links
    normal = group.nodes.new("GeometryNodeInputNormal")
    blur = group.nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    links.new(normal.outputs[0], blur.inputs["Value"])
    blur.inputs["Iterations"].default_value = NORMAL_SMOOTH_ITERATIONS
    smoothed = blur.outputs[0]
    return smoothed, build_island_normal(group, normal.outputs[0])


def build_normal_direction(group, controls, smoothed, average, weight):
    """Stabilize boundary normals and bypass the blur at the island direction."""
    nodes, links = group.nodes, group.links
    boundary_blend = _math(
        group, "MULTIPLY", BOUNDARY_NORMAL_BLEND,
        read_float_attribute(group, BOUNDARY_FALLOFF_ATTRIBUTE),
    )
    weight = _math(
        group, "ADD", weight,
        _math(group, "MULTIPLY", _math(group, "SUBTRACT", 1.0, weight), boundary_blend),
    )
    difference = group.nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(average, difference.inputs[0])
    links.new(smoothed, difference.inputs[1])
    lean = _math(
        group, "MULTIPLY", _math(group, "SUBTRACT", 1.0, weight),
        controls.outputs["Normal Bias"],
    )
    offset = group.nodes.new("ShaderNodeVectorMath")
    offset.operation = "SCALE"
    links.new(difference.outputs["Vector"], offset.inputs[0])
    links.new(lean, offset.inputs[3])
    direction = group.nodes.new("ShaderNodeVectorMath")
    direction.operation = "ADD"
    links.new(average, direction.inputs[0])
    links.new(offset.outputs["Vector"], direction.inputs[1])
    normalize = group.nodes.new("ShaderNodeVectorMath")
    normalize.operation = "NORMALIZE"
    links.new(direction.outputs["Vector"], normalize.inputs[0])
    is_average = compare_node(group, "EQUAL", controls.outputs["Normal Bias"], 0.0)
    is_average.node.inputs["Epsilon"].default_value = 0.0
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "VECTOR"
    links.new(is_average, choose.inputs["Switch"])
    links.new(normalize.outputs["Vector"], choose.inputs["False"])
    links.new(average, choose.inputs["True"])
    return choose.outputs[0]


def build_inflation_amount(group, controls, is_shell):
    """Balloon scales the profile by Depth Scale, Shell moves a fixed distance."""
    nodes, links = group.nodes, group.links
    thickness = _math(
        group, "MULTIPLY", controls.outputs["Thickness"],
        _math(group, "ADD", BALLOON_THICKNESS_BASE, controls.outputs["Depth Scale"]),
    )
    balloon = _math(
        group, "MULTIPLY", read_float_attribute(group, "o_balloon"), thickness,
    )
    amount = nodes.new("GeometryNodeSwitch")
    amount.input_type = "FLOAT"
    links.new(is_shell, amount.inputs["Switch"])
    links.new(balloon, amount.inputs["False"])
    links.new(controls.outputs["Shell Thickness"], amount.inputs["True"])
    return amount.outputs[0]


def build_side_ring_target(group, paired_position, paired_normal):
    """Blend the paired midpoint toward a stable normal-guided outer target."""
    nodes, links = group.nodes, group.links
    position = nodes.new("GeometryNodeInputPosition")
    total = nodes.new("ShaderNodeVectorMath")
    total.operation = "ADD"
    links.new(position.outputs["Position"], total.inputs[0])
    links.new(paired_position, total.inputs[1])
    midpoint = nodes.new("ShaderNodeVectorMath")
    midpoint.operation = "SCALE"
    midpoint.inputs[3].default_value = 0.5
    links.new(total.outputs["Vector"], midpoint.inputs[0])

    normal = nodes.new("GeometryNodeInputNormal")
    aligned_normal = nodes.new("ShaderNodeVectorMath")
    aligned_normal.operation = "SUBTRACT"
    links.new(normal.outputs["Normal"], aligned_normal.inputs[0])
    links.new(paired_normal, aligned_normal.inputs[1])
    surface_normal = nodes.new("ShaderNodeVectorMath")
    surface_normal.operation = "NORMALIZE"
    links.new(aligned_normal.outputs["Vector"], surface_normal.inputs[0])

    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    blur.inputs["Iterations"].default_value = 1
    blur.inputs["Weight"].default_value = 1.0
    links.new(position.outputs["Position"], blur.inputs["Value"])
    inward = nodes.new("ShaderNodeVectorMath")
    inward.operation = "SUBTRACT"
    links.new(blur.outputs["Value"], inward.inputs[0])
    links.new(position.outputs["Position"], inward.inputs[1])
    normal_amount = nodes.new("ShaderNodeVectorMath")
    normal_amount.operation = "DOT_PRODUCT"
    links.new(inward.outputs["Vector"], normal_amount.inputs[0])
    links.new(surface_normal.outputs["Vector"], normal_amount.inputs[1])
    normal_component = nodes.new("ShaderNodeVectorMath")
    normal_component.operation = "SCALE"
    links.new(surface_normal.outputs["Vector"], normal_component.inputs[0])
    links.new(normal_amount.outputs["Value"], normal_component.inputs[3])
    tangent_inward = nodes.new("ShaderNodeVectorMath")
    tangent_inward.operation = "SUBTRACT"
    links.new(inward.outputs["Vector"], tangent_inward.inputs[0])
    links.new(normal_component.outputs["Vector"], tangent_inward.inputs[1])
    outward = nodes.new("ShaderNodeVectorMath")
    outward.operation = "NORMALIZE"
    links.new(tangent_inward.outputs["Vector"], outward.inputs[0])

    span = nodes.new("ShaderNodeVectorMath")
    span.operation = "DISTANCE"
    links.new(position.outputs["Position"], span.inputs[0])
    links.new(paired_position, span.inputs[1])
    offset = nodes.new("ShaderNodeVectorMath")
    offset.operation = "SCALE"
    links.new(outward.outputs["Vector"], offset.inputs[0])
    links.new(
        _math(group, "MULTIPLY", span.outputs["Value"], -SIDE_RING_OFFSET_FACTOR),
        offset.inputs[3],
    )
    target = nodes.new("ShaderNodeVectorMath")
    target.operation = "ADD"
    links.new(midpoint.outputs["Vector"], target.inputs[0])
    links.new(offset.outputs["Vector"], target.inputs[1])
    return target.outputs["Vector"]


def build_thickness_strength(group, displacement):
    """Fade thickness-dependent details in over a short displacement range."""
    node = group.nodes.new("ShaderNodeMapRange")
    node.interpolation_type = "SMOOTHSTEP"
    node.clamp = True
    group.links.new(displacement, node.inputs["Value"])
    node.inputs["From Min"].default_value = 0.0
    node.inputs["From Max"].default_value = THICKNESS_TRANSITION
    node.inputs["To Min"].default_value = 0.0
    node.inputs["To Max"].default_value = 1.0
    return _math(group, "POWER", node.outputs["Result"], 0.5)


def build_bridge_uv(group, thickness_strength):
    """Return leaf and Side UVs derived from the same local blur."""
    nodes, links = group.nodes, group.links
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    point_uv = evaluate_field(
        group, uv.outputs["Attribute"], "FLOAT_VECTOR", "POINT",
    )
    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    blur.inputs["Iterations"].default_value = SIDE_UV_BLUR_ITERATIONS
    blur.inputs["Weight"].default_value = 1.0
    links.new(point_uv, blur.inputs["Value"])
    difference = nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(blur.outputs["Value"], difference.inputs[0])
    links.new(point_uv, difference.inputs[1])
    influence = read_float_attribute(group, BOUNDARY_FALLOFF_ATTRIBUTE)
    leaf_offset = nodes.new("ShaderNodeVectorMath")
    leaf_offset.operation = "SCALE"
    links.new(difference.outputs["Vector"], leaf_offset.inputs[0])
    links.new(
        _math(
            group,
            "MULTIPLY",
            _math(group, "MULTIPLY", LEAF_UV_PULL, influence),
            thickness_strength,
        ),
        leaf_offset.inputs[3],
    )
    leaf_uv = nodes.new("ShaderNodeVectorMath")
    leaf_uv.operation = "ADD"
    links.new(point_uv, leaf_uv.inputs[0])
    links.new(leaf_offset.outputs["Vector"], leaf_uv.inputs[1])
    return leaf_uv.outputs["Vector"], point_uv, influence


def prepare_bridge_uv(group, leaf, thickness_strength):
    """Adjust leaf boundary UVs and store the matching Side ring UV target."""
    nodes, links = group.nodes, group.links
    base_uv, top_uv, influence = build_bridge_uv(group, thickness_strength)
    prepared = store_vector_attribute(
        group, leaf, SIDE_BASE_UV_ATTRIBUTE, base_uv,
    )
    prepared = store_vector_attribute(
        group, prepared, SIDE_TOP_UV_ATTRIBUTE, top_uv,
    )
    store_uv = nodes.new("GeometryNodeStoreNamedAttribute")
    store_uv.data_type, store_uv.domain = "FLOAT2", "CORNER"
    store_uv.inputs["Name"].default_value = "UVMap"
    links.new(prepared, store_uv.inputs["Geometry"])
    links.new(compare_node(group, "GREATER_THAN", influence, 1e-8), store_uv.inputs["Selection"])
    links.new(read_vector_attribute(group, SIDE_BASE_UV_ATTRIBUTE), store_uv.inputs["Value"])
    return store_uv.outputs["Geometry"]


def build_sides(group, leaves):
    """Extrude both disconnected leaf boundaries to their shared Side ring."""
    nodes, links = group.nodes, group.links
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "EDGES"
    extrude.inputs["Offset"].default_value = (0.0, -1.0, 0.0)
    links.new(leaves, extrude.inputs["Mesh"])
    links.new(edge_boundary_field(nodes, links), extrude.inputs["Selection"])
    place_top = nodes.new("GeometryNodeSetPosition")
    links.new(extrude.outputs["Mesh"], place_top.inputs["Geometry"])
    links.new(extrude.outputs["Top"], place_top.inputs["Selection"])
    links.new(read_vector_attribute(group, SIDE_RING_TARGET_ATTRIBUTE), place_top.inputs["Position"])
    side_uv = nodes.new("GeometryNodeSwitch")
    side_uv.input_type = "VECTOR"
    links.new(extrude.outputs["Top"], side_uv.inputs["Switch"])
    links.new(read_vector_attribute(group, SIDE_BASE_UV_ATTRIBUTE), side_uv.inputs["False"])
    links.new(read_vector_attribute(group, SIDE_TOP_UV_ATTRIBUTE), side_uv.inputs["True"])
    store_uv = nodes.new("GeometryNodeStoreNamedAttribute")
    store_uv.data_type, store_uv.domain = "FLOAT2", "CORNER"
    store_uv.inputs["Name"].default_value = "UVMap"
    links.new(place_top.outputs["Geometry"], store_uv.inputs["Geometry"])
    links.new(extrude.outputs["Side"], store_uv.inputs["Selection"])
    links.new(
        evaluate_field(group, side_uv.outputs[0], "FLOAT_VECTOR", "POINT"),
        store_uv.inputs["Value"],
    )
    sides = nodes.new("GeometryNodeSeparateGeometry")
    sides.domain = "FACE"
    links.new(store_uv.outputs["Geometry"], sides.inputs["Geometry"])
    links.new(extrude.outputs["Side"], sides.inputs["Selection"])
    return sides.outputs["Selection"]


def build_solid(
    group, surface, amount, normal, is_shell, has_thickness,
    thickness_strength, controls,
):
    """Inflate the projected surface and bridge both leaves through one Side ring."""
    nodes, links = group.nodes, group.links
    balloon_profile = read_float_attribute(group, "o_balloon")

    def offset(distance):
        result = nodes.new("ShaderNodeVectorMath")
        result.operation = "SCALE"
        links.new(normal, result.inputs[0])
        links.new(distance, result.inputs[3])
        return result.outputs[0]

    # The front leaf moves by Thickness x o_balloon x Front Inflation, independent of
    # the Depth Scale that scales the rear recession.
    inflation = _math(
        group, "MULTIPLY",
        _math(
            group, "MULTIPLY", balloon_profile,
            controls.outputs["Thickness"],
        ),
        controls.outputs["Front Inflation"],
    )
    front_amount = nodes.new("GeometryNodeSwitch")
    front_amount.input_type = "FLOAT"
    links.new(is_shell, front_amount.inputs["Switch"])
    links.new(inflation, front_amount.inputs["False"])
    front_amount.inputs["True"].default_value = 0.0

    front = nodes.new("GeometryNodeSetPosition")
    links.new(surface, front.inputs["Geometry"])
    links.new(offset(front_amount.outputs[0]), front.inputs["Offset"])

    # Match the Faces Extrude displacement domain while keeping an open rear leaf.
    span = _math(group, "MULTIPLY", amount, -1.0)
    rear = nodes.new("GeometryNodeSetPosition")
    links.new(surface, rear.inputs["Geometry"])
    links.new(evaluate_field(group, offset(span), "FLOAT_VECTOR", "FACE"), rear.inputs["Offset"])

    # The rear surface smooths in proportion to its thickness and the balloon profile,
    # so thin shells and cut boundaries keep their exact positions.
    thickness = nodes.new("GeometryNodeSwitch")
    thickness.input_type = "FLOAT"
    links.new(is_shell, thickness.inputs["Switch"])
    links.new(controls.outputs["Thickness"], thickness.inputs["False"])
    links.new(controls.outputs["Shell Thickness"], thickness.inputs["True"])
    weight = _math(
        group, "MULTIPLY", _math(group, "MINIMUM", thickness.outputs[0], 1.0),
        _math(group, "POWER", balloon_profile, 0.5),
    )
    position = nodes.new("GeometryNodeInputPosition")
    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    blur.inputs["Weight"].default_value = 1.0
    links.new(position.outputs["Position"], blur.inputs["Value"])
    links.new(group_input(nodes, {"Rear Smooth"}).outputs["Rear Smooth"], blur.inputs["Iterations"])
    difference = nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(blur.outputs["Value"], difference.inputs[0])
    links.new(position.outputs["Position"], difference.inputs[1])
    smooth_offset = nodes.new("ShaderNodeVectorMath")
    smooth_offset.operation = "SCALE"
    links.new(difference.outputs["Vector"], smooth_offset.inputs[0])
    links.new(weight, smooth_offset.inputs[3])
    smoothed = nodes.new("GeometryNodeSetPosition")
    links.new(rear.outputs["Geometry"], smoothed.inputs["Geometry"])
    links.new(smooth_offset.outputs["Vector"], smoothed.inputs["Offset"])
    flipped_rear = nodes.new("GeometryNodeFlipFaces")
    links.new(smoothed.outputs["Geometry"], flipped_rear.inputs["Mesh"])

    marked_front = store_int_attribute(
        group, front.outputs["Geometry"], LEAF_ID_ATTRIBUTE, 0,
    )
    marked_rear = store_int_attribute(
        group, flipped_rear.outputs["Mesh"], LEAF_ID_ATTRIBUTE, 1,
    )
    leaves = nodes.new("GeometryNodeJoinGeometry")
    links.new(marked_front, leaves.inputs["Geometry"])
    links.new(marked_rear, leaves.inputs["Geometry"])
    smoothing_input = nodes.new("GeometryNodeSwitch")
    smoothing_input.input_type = "GEOMETRY"
    links.new(has_thickness, smoothing_input.inputs["Switch"])
    links.new(marked_front, smoothing_input.inputs["False"])
    links.new(leaves.outputs["Geometry"], smoothing_input.inputs["True"])
    smoothing_geometry = remove_attribute_pattern(
        group, smoothing_input.outputs[0], f"{FRONT_NORMAL_ATTRIBUTE}*",
    )
    smoothed_leaves = pinned_smooth(
        group,
        smoothing_geometry,
        group_input(nodes, {"Boundary Smooth"}).outputs["Boundary Smooth"],
        read_float_attribute(group, BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE),
    )
    smoothed_leaves = remove_attribute_pattern(
        group, smoothed_leaves, f"{BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE}*",
    )
    # Both leaves remain disconnected, so one UV blur preserves each leaf's values.
    bridge_uv = nodes.new("GeometryNodeSwitch")
    bridge_uv.input_type = "GEOMETRY"
    links.new(has_thickness, bridge_uv.inputs["Switch"])
    links.new(smoothed_leaves, bridge_uv.inputs["False"])
    links.new(
        prepare_bridge_uv(group, smoothed_leaves, thickness_strength),
        bridge_uv.inputs["True"],
    )
    is_rear = compare_node(
        group, "EQUAL", read_int_attribute(group, LEAF_ID_ATTRIBUTE), 1, data_type="INT",
    )
    separate = nodes.new("GeometryNodeSeparateGeometry")
    separate.domain = "POINT"
    links.new(bridge_uv.outputs[0], separate.inputs["Geometry"])
    links.new(is_rear, separate.inputs["Selection"])
    rear_geometry = separate.outputs["Selection"]
    front_leaf = separate.outputs["Inverted"]

    # Compute one source-indexed Side ring target on the Front, then sample the
    # same target onto the Rear so both Extrudes remain exactly weldable.
    rear_lookup = nodes.new("GeometryNodeSortElements")
    rear_lookup.domain = "POINT"
    links.new(rear_geometry, rear_lookup.inputs["Geometry"])
    source_index = read_int_attribute(group, LEAF_SOURCE_INDEX_ATTRIBUTE)
    links.new(source_index, rear_lookup.inputs["Sort Weight"])
    position = nodes.new("GeometryNodeInputPosition")
    normal = nodes.new("GeometryNodeInputNormal")
    rear_position = sample_field(
        group, rear_lookup.outputs["Geometry"], position.outputs["Position"], "FLOAT_VECTOR",
        index=source_index,
    )
    rear_normal = sample_field(
        group, rear_lookup.outputs["Geometry"], normal.outputs["Normal"], "FLOAT_VECTOR",
        index=source_index,
    )
    front_geometry = store_vector_attribute(
        group,
        front_leaf,
        SIDE_RING_TARGET_ATTRIBUTE,
        build_side_ring_target(
            group,
            rear_position,
            rear_normal,
        ),
    )
    front_lookup = nodes.new("GeometryNodeSortElements")
    front_lookup.domain = "POINT"
    links.new(front_geometry, front_lookup.inputs["Geometry"])
    links.new(source_index, front_lookup.inputs["Sort Weight"])
    side_ring_target = sample_field(
        group,
        front_lookup.outputs["Geometry"],
        read_vector_attribute(group, SIDE_RING_TARGET_ATTRIBUTE),
        "FLOAT_VECTOR",
        index=source_index,
    )
    rear_geometry = store_vector_attribute(
        group, rear_geometry, SIDE_RING_TARGET_ATTRIBUTE, side_ring_target,
    )
    side_leaves = nodes.new("GeometryNodeJoinGeometry")
    links.new(front_geometry, side_leaves.inputs["Geometry"])
    links.new(rear_geometry, side_leaves.inputs["Geometry"])
    sides = build_sides(group, side_leaves.outputs["Geometry"])
    back = nodes.new("GeometryNodeJoinGeometry")
    links.new(rear_geometry, back.inputs["Geometry"])
    links.new(sides, back.inputs["Geometry"])
    back_geometry = store_float_attribute(
        group, back.outputs["Geometry"], NORMAL_REDUCTION_ATTRIBUTE_NAME, 1.0,
    )
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(front_geometry, join.inputs["Geometry"])
    links.new(back_geometry, join.inputs["Geometry"])
    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "ALL"
    merge.inputs["Distance"].default_value = 1e-6
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])
    result = nodes.new("GeometryNodeSwitch")
    result.input_type = "GEOMETRY"
    links.new(has_thickness, result.inputs["Switch"])
    links.new(front_leaf, result.inputs["False"])
    links.new(merge.outputs["Geometry"], result.inputs["True"])
    return result.outputs[0]


def _build_depth_surface(group, geometry, controls):
    """Project the depth image and inflate the projected surface into a solid."""
    links = group.links
    split = controls.outputs["Depth Split"]
    image = controls.outputs["Depth Image"]
    scale = controls.outputs["Uniform Scale"]
    geometry, corner_camera, cut_vertex = split_depth_surface(
        group, geometry, sample_face_camera(group, image), split, controls.outputs["Reference Depth"],
        controls.outputs["Depth Scale"], triangles=True,
    )
    geometry, cut_vertex, previous_boundary, has_limited = limit_depth_surface(
        group, geometry, corner_camera, cut_vertex,
        scale, controls.outputs["Reference Depth"], controls.outputs["Depth Scale"],
        controls.outputs["Depth Limit"],
    )
    # Split and Depth Limit can both leave triangular ears whose three vertices
    # lie on the open boundary. Clean the combined result once.
    geometry = remove_boundary_triangles(group, geometry)
    boundary = edge_boundary_field(group.nodes, group.links)
    limit_boundary = boolean_node(
        group, "AND", has_limited,
        boolean_node(
            group, "AND", boundary, boolean_node(group, "NOT", previous_boundary),
        ),
    )
    cut = evaluate_field(
        group,
        boolean_node(
            group, "AND", boundary,
            boolean_node(group, "OR", cut_vertex, limit_boundary),
        ),
        "FLOAT", "POINT",
    )
    # Depth Split and Depth Limit cuts taper the profile; the original outline keeps its thickness.
    geometry = taper_split_profile(group, geometry, cut)
    geometry, cut_boundary = store_boolean_attribute(
        group, geometry, CUT_BOUNDARY_ATTRIBUTE, cut,
    )
    camera = build_surface_camera(
        group, _position_field(group, image), corner_camera, cut_vertex, split,
    )
    projection = project_depth_surface(
        group, geometry, camera, scale, controls.outputs["Reference Depth"], controls.outputs["Depth Scale"],
    )
    # The mode field is shared by the thickness and direction choices.
    mode = group.nodes.new("GeometryNodeMenuSwitch")
    mode.data_type = "BOOLEAN"
    for item, name in zip(mode.enum_items, ("Balloon", "Shell")):
        item.name = name
    links.new(controls.outputs["Mode"], mode.inputs["Menu"])
    mode.inputs["Balloon"].default_value = False
    mode.inputs["Shell"].default_value = True
    is_shell = mode.outputs[0]
    amount = build_inflation_amount(group, controls, is_shell)
    statistics = group.nodes.new("GeometryNodeAttributeStatistic")
    statistics.data_type, statistics.domain = "FLOAT", "POINT"
    links.new(projection, statistics.inputs["Geometry"])
    links.new(amount, statistics.inputs["Attribute"])
    has_thickness = compare_node(group, "GREATER_THAN", statistics.outputs["Max"], 1e-6)
    thickness_strength = build_thickness_strength(group, statistics.outputs["Max"])
    smooth_enabled = compare_node(
        group,
        "GREATER_THAN",
        controls.outputs["Boundary Smooth"],
        0,
        data_type="INT",
    )
    falloff_projection = store_float_attribute(
        group,
        projection,
        BOUNDARY_FALLOFF_ATTRIBUTE,
        boundary_influence(group, boundary=boundary, iterations=SIDE_UV_INFLUENCE_ITERATIONS),
    )
    falloff_enabled = group.nodes.new("GeometryNodeSwitch")
    falloff_enabled.input_type = "GEOMETRY"
    links.new(
        boolean_node(group, "OR", smooth_enabled, has_thickness),
        falloff_enabled.inputs["Switch"],
    )
    links.new(projection, falloff_enabled.inputs["False"])
    links.new(falloff_projection, falloff_enabled.inputs["True"])
    projection = falloff_enabled.outputs["Output"]
    cut_falloff = boundary_influence(
        group,
        boundary=cut_boundary,
        iterations=SIDE_UV_INFLUENCE_ITERATIONS,
    )
    smooth_weight = _math(
        group,
        "MAXIMUM",
        cut_falloff,
        _math(
            group,
            "MULTIPLY",
            read_float_attribute(group, BOUNDARY_FALLOFF_ATTRIBUTE),
            0.1,
        ),
    )
    weighted_projection = store_float_attribute(
        group, projection, BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE, smooth_weight,
    )
    boundary_weight = group.nodes.new("GeometryNodeSwitch")
    boundary_weight.input_type = "GEOMETRY"
    links.new(smooth_enabled, boundary_weight.inputs["Switch"])
    links.new(projection, boundary_weight.inputs["False"])
    links.new(weighted_projection, boundary_weight.inputs["True"])
    projection = remove_attribute_pattern(
        group, boundary_weight.outputs["Output"], f"{CUT_BOUNDARY_ATTRIBUTE}*",
    )
    source_index = group.nodes.new("GeometryNodeInputIndex")
    projection = store_int_attribute(
        group, projection, LEAF_SOURCE_INDEX_ATTRIBUTE, source_index.outputs["Index"],
    )
    profile = build_profile_weight(group, projection)
    smoothed, average = build_smoothed_normals(group)
    weight = build_normal_weight(group, is_shell, profile)
    # Material normal strength: the balloon profile gates it, Depth Scale attenuates it.
    inflated = group.nodes.new("GeometryNodeSwitch")
    inflated.input_type = "FLOAT"
    links.new(is_shell, inflated.inputs["Switch"])
    links.new(profile, inflated.inputs["False"])
    inflated.inputs["True"].default_value = 1.0
    normal_strength = _math(
        group,
        "SUBTRACT",
        1.0,
        _math(
            group,
            "MULTIPLY",
            thickness_strength,
            _math(group, "SUBTRACT", 1.0, inflated.outputs[0]),
        ),
    )
    reduction = _math(
        group, "SUBTRACT", 1.0,
        _math(
            group, "MULTIPLY",
            _math(group, "MINIMUM", controls.outputs["Depth Scale"], 1.0),
            normal_strength,
        ),
    )
    reduction.node.use_clamp = True
    projection = store_float_attribute(
        group, projection, NORMAL_REDUCTION_ATTRIBUTE_NAME, reduction,
    )
    # The rear leaf inflates along the negated front direction, so one direction is
    # carried across the extrusion instead of being re-evaluated on the moved surface.
    normal_projection = store_vector_attribute(
        group, projection, FRONT_NORMAL_ATTRIBUTE,
        build_normal_direction(group, controls, smoothed, average, weight),
    )
    normal_enabled = group.nodes.new("GeometryNodeSwitch")
    normal_enabled.input_type = "GEOMETRY"
    links.new(has_thickness, normal_enabled.inputs["Switch"])
    links.new(projection, normal_enabled.inputs["False"])
    links.new(normal_projection, normal_enabled.inputs["True"])
    projection = normal_enabled.outputs["Output"]
    solid = build_solid(
        group, projection, amount,
        read_vector_attribute(group, FRONT_NORMAL_ATTRIBUTE),
        is_shell, has_thickness, thickness_strength, controls,
    )
    return remove_attribute_pattern(group, solid, "_o_*")


def build_image_depth_cutout_group():
    name = NODE_GROUP_NAME
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    group.is_modifier, group.use_fake_user = (True, True)
    group.color_tag = 'GEOMETRY'
    interface_socket(group, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    interface_socket(group, 'Mode', 'INPUT', 'NodeSocketMenu')
    float_input(group, 'Thickness', 0.0, maximum=2.0).description = 'Control how much the surface bulges in Balloon mode. Zero removes the bulge.'
    float_input(group, 'Front Inflation', 0.3, maximum=1, subtype='FACTOR').description = 'Control how much the front surface bulges in Balloon mode, as a share of the balloon thickness. Zero keeps the original front surface.'
    float_input(group, 'Shell Thickness', 0.0, maximum=1.0, subtype='DISTANCE').description = 'Add thickness behind the original surface while keeping the front surface in place.'
    float_input(group, 'Depth Scale', 1.0, maximum=2.0)
    float_input(group, 'Depth Split', 0.1, maximum=1, subtype='FACTOR').description = 'Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps.'
    float_input(group, 'Depth Limit', 1.0, minimum=-1.0, subtype='DISTANCE').description = 'Remove faces whose center lies beyond this distance behind the reference plane.'
    options = group.interface.new_panel(name='Options', default_closed=True)
    boundary_smooth = interface_socket(group, 'Boundary Smooth', 'INPUT', 'NodeSocketInt', options)
    boundary_smooth.default_value, boundary_smooth.min_value, boundary_smooth.max_value = 4, 0, 16
    boundary_smooth.description = 'Smooth geometry near the original outline and Depth Split edges. Zero disables boundary smoothing.'
    rear_smooth = interface_socket(group, 'Rear Smooth', 'INPUT', 'NodeSocketInt', options)
    rear_smooth.default_value, rear_smooth.min_value, rear_smooth.max_value = 8, 0, 16
    rear_smooth.description = 'Soften the rear surface where the balloon is thick. The strength follows the square root of the balloon profile for a flatter transition while thin geometry and cut boundaries keep their positions.'
    float_input(group, 'Normal Bias', 0.0, minimum=-2.0, maximum=2.0, parent=options).description = 'Bias the thickness direction: zero uses the island average without normal blur, negative values turn toward the boundary-stabilized local normal, and positive values turn away from it.'
    float_input(group, 'Reference Depth', 1.0, subtype='DISTANCE', parent=options)
    data = group.interface.new_panel(name='Data', default_closed=True)
    float_input(group, 'Uniform Scale', 1.0, parent=data).hide_in_modifier = True
    interface_socket(group, 'Depth Image', 'INPUT', 'NodeSocketImage', data).hide_in_modifier = True
    interface_socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    controls = group_input(group.nodes, set())
    geometry = _build_depth_surface(group, controls.outputs['Geometry'], controls)
    _shade_output(group, geometry)
    prepare_node_group(group)
    for item in group.interface.items_tree:
        if item.item_type != 'SOCKET' or item.in_out != 'INPUT':
            continue
        if item.name == 'Mode':
            item.default_value = 'Balloon'
        elif item.name == 'Shell Thickness':
            item.name = 'Thickness'
    return group
