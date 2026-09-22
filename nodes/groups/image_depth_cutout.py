"""Build O Image Depth Cutout."""
import bpy
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import (
    interface_socket, group_input, float_input, boolean_node, read_float_attribute, read_vector_attribute,
    read_int_attribute, store_float_attribute, store_vector_attribute, store_int_attribute,
    store_boolean_attribute, remove_attribute_pattern, prepare_node_group, evaluate_field,
    compare_node, sample_field,
)
from ..common.boundary_smoothing import cut_boundary_influence
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
CUT_BOUNDARY_ATTRIBUTE = "_o_cut_boundary"
LEAF_ID_ATTRIBUTE = "_o_leaf_id"
LEAF_SOURCE_INDEX_ATTRIBUTE = "_o_leaf_source_index"
REAR_TARGET_ATTRIBUTE = "_o_rear_target"
BALLOON_THICKNESS_BASE = 1.0
NORMAL_SMOOTH_ITERATIONS = 256


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
    """Average the smoothed normals of one connected mesh island."""
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
    """Return the smoothed normals and the average normal of each mesh island."""
    nodes, links = group.nodes, group.links
    normal = group.nodes.new("GeometryNodeInputNormal")
    blur = group.nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    links.new(normal.outputs[0], blur.inputs["Value"])
    blur.inputs["Iterations"].default_value = NORMAL_SMOOTH_ITERATIONS
    smoothed = blur.outputs[0]
    return smoothed, build_island_normal(group, smoothed)


def build_normal_direction(group, controls, smoothed, average, weight):
    """Blend the smoothed normal against the island average normal."""
    nodes, links = group.nodes, group.links
    difference = group.nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(average, difference.inputs[0])
    links.new(smoothed, difference.inputs[1])
    lean = _math(
        group, "MULTIPLY", _math(group, "SUBTRACT", 1.0, weight),
        controls.outputs["Edge Turn"],
    )
    blend = _math(group, "ADD", weight, lean)
    offset = group.nodes.new("ShaderNodeVectorMath")
    offset.operation = "SCALE"
    links.new(difference.outputs["Vector"], offset.inputs[0])
    links.new(blend, offset.inputs[3])
    direction = group.nodes.new("ShaderNodeVectorMath")
    direction.operation = "ADD"
    links.new(smoothed, direction.inputs[0])
    links.new(offset.outputs["Vector"], direction.inputs[1])
    normalize = group.nodes.new("ShaderNodeVectorMath")
    normalize.operation = "NORMALIZE"
    links.new(direction.outputs["Vector"], normalize.inputs[0])
    return normalize.outputs["Vector"]


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


def build_solid(group, surface, amount, normal, is_shell, has_thickness, controls):
    """Inflate the projected surface into a front leaf, wall and rear leaf."""
    nodes, links = group.nodes, group.links

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
            group, "MULTIPLY", read_float_attribute(group, "o_balloon"),
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
        _math(group, "POWER", read_float_attribute(group, "o_balloon"), 0.5),
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
    smoothed_leaves = pinned_smooth(
        group,
        smoothing_input.outputs[0],
        group_input(nodes, {"Boundary Smooth"}).outputs["Boundary Smooth"],
        read_float_attribute(group, BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE),
    )
    is_rear = compare_node(
        group, "EQUAL", read_int_attribute(group, LEAF_ID_ATTRIBUTE), 1, data_type="INT",
    )
    separate = nodes.new("GeometryNodeSeparateGeometry")
    separate.domain = "POINT"
    links.new(smoothed_leaves, separate.inputs["Geometry"])
    links.new(is_rear, separate.inputs["Selection"])
    rear_geometry = separate.outputs["Selection"]
    front_leaf = separate.outputs["Inverted"]

    # Normalize the lookup order by the source index, then store the absolute rear
    # target on the front before extracting its boundary edges.
    rear_lookup = nodes.new("GeometryNodeSortElements")
    rear_lookup.domain = "POINT"
    links.new(rear_geometry, rear_lookup.inputs["Geometry"])
    links.new(read_int_attribute(group, LEAF_SOURCE_INDEX_ATTRIBUTE), rear_lookup.inputs["Sort Weight"])
    position = nodes.new("GeometryNodeInputPosition")
    rear_position = sample_field(
        group, rear_lookup.outputs["Geometry"], position.outputs["Position"], "FLOAT_VECTOR",
        index=read_int_attribute(group, LEAF_SOURCE_INDEX_ATTRIBUTE),
    )
    front_geometry = store_vector_attribute(
        group, front_leaf, REAR_TARGET_ATTRIBUTE, rear_position,
    )

    boundary = edge_boundary_field(nodes, links)

    # Edges Extrude builds only the wall topology. Its Offset is edge-domain, so
    # the generated top points are explicitly placed at their propagated targets.
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "EDGES"
    extrude.inputs["Offset"].default_value = (0.0, -1.0, 0.0)
    links.new(front_geometry, extrude.inputs["Mesh"])
    links.new(boundary, extrude.inputs["Selection"])
    place_top = nodes.new("GeometryNodeSetPosition")
    links.new(extrude.outputs["Mesh"], place_top.inputs["Geometry"])
    links.new(extrude.outputs["Top"], place_top.inputs["Selection"])
    links.new(read_vector_attribute(group, REAR_TARGET_ATTRIBUTE), place_top.inputs["Position"])
    sides = nodes.new("GeometryNodeSeparateGeometry")
    sides.domain = "FACE"
    links.new(place_top.outputs["Geometry"], sides.inputs["Geometry"])
    links.new(extrude.outputs["Side"], sides.inputs["Selection"])

    back = nodes.new("GeometryNodeJoinGeometry")
    links.new(rear_geometry, back.inputs["Geometry"])
    links.new(sides.outputs["Selection"], back.inputs["Geometry"])
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
    weighted_projection = store_float_attribute(
        group,
        projection,
        BOUNDARY_SMOOTH_WEIGHT_ATTRIBUTE,
        cut_boundary_influence(group, cut_boundary),
    )
    smooth_enabled = compare_node(
        group,
        "GREATER_THAN",
        controls.outputs["Boundary Smooth"],
        0,
        data_type="INT",
    )
    boundary_weight = group.nodes.new("GeometryNodeSwitch")
    boundary_weight.input_type = "GEOMETRY"
    links.new(smooth_enabled, boundary_weight.inputs["Switch"])
    links.new(projection, boundary_weight.inputs["False"])
    links.new(weighted_projection, boundary_weight.inputs["True"])
    projection = boundary_weight.outputs["Output"]
    source_index = group.nodes.new("GeometryNodeInputIndex")
    projection = store_int_attribute(
        group, projection, LEAF_SOURCE_INDEX_ATTRIBUTE, source_index.outputs["Index"],
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
    profile = build_profile_weight(group, projection)
    smoothed, average = build_smoothed_normals(group)
    weight = build_normal_weight(group, is_shell, profile)
    # Material normal strength: the balloon profile gates it, Depth Scale attenuates it.
    inflated = group.nodes.new("GeometryNodeSwitch")
    inflated.input_type = "FLOAT"
    links.new(is_shell, inflated.inputs["Switch"])
    links.new(profile, inflated.inputs["False"])
    inflated.inputs["True"].default_value = 1.0
    normal_strength = group.nodes.new("GeometryNodeSwitch")
    normal_strength.input_type = "FLOAT"
    links.new(has_thickness, normal_strength.inputs["Switch"])
    normal_strength.inputs["False"].default_value = 1.0
    links.new(inflated.outputs[0], normal_strength.inputs["True"])
    reduction = _math(
        group, "SUBTRACT", 1.0,
        _math(group, "MULTIPLY", controls.outputs["Depth Scale"], normal_strength.outputs[0]),
    )
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
        is_shell, has_thickness, controls,
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
    float_input(group, 'Edge Turn', 1.0, minimum=-3.0, maximum=3.0, parent=options).description = 'Turn the outline direction: zero follows the smoothed normal, one reaches the island average normal, two mirrors the smoothed normal across it, and higher or negative values keep turning either way.'
    float_input(group, 'Front Inflation', 0.2, maximum=1, subtype='FACTOR', parent=options).description = 'Control how much the front surface bulges in Balloon mode, as a share of the balloon thickness. Zero keeps the original front surface.'
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
