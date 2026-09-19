"""Build O Image Depth Cutout."""
import bpy
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import (
    interface_socket, group_input, float_input, boolean_node, read_float_attribute, read_vector_attribute,
    store_float_attribute, store_vector_attribute, remove_attribute_pattern,
    prepare_node_group, evaluate_field, compare_node,
)
from ..common.boundary_smoothing import smooth_cut_boundary
from ..common.cutout import _position_field, _shade_output
from ..common.depth_surface import _math, project_depth_surface, build_surface_camera, split_depth_surface, sample_face_camera
from ..common.smoothing import edge_boundary_field
from ..common.cutout_boundary import remove_boundary_triangles, taper_split_profile


NODE_GROUP_NAME = "O Image Depth Cutout"
FRONT_NORMAL_ATTRIBUTE = "_o_front_normal"
BALLOON_THICKNESS_BASE = 1.0
NORMAL_SMOOTH_ITERATIONS = 256
SOLID_WELD_SCALE = 1e-3


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


def build_solid(group, surface, amount, normal, is_shell, controls, weld_distance):
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

    # The rear leaf inflates along the negated front direction, straight from the
    # untouched surface so the front offset cannot drag it along.
    span = _math(group, "MULTIPLY", amount, -1.0)
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    links.new(surface, extrude.inputs["Mesh"])
    links.new(offset(span), extrude.inputs["Offset"])

    # The rear surface smooths in proportion to its thickness and the balloon profile,
    # so thin shells and cut boundaries keep their exact positions.
    thickness = nodes.new("GeometryNodeSwitch")
    thickness.input_type = "FLOAT"
    links.new(is_shell, thickness.inputs["Switch"])
    links.new(controls.outputs["Thickness"], thickness.inputs["False"])
    links.new(controls.outputs["Shell Thickness"], thickness.inputs["True"])
    weight = _math(
        group, "MULTIPLY", _math(group, "MINIMUM", thickness.outputs[0], 1.0),
        read_float_attribute(group, "o_balloon"),
    )
    position = nodes.new("GeometryNodeInputPosition")
    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT_VECTOR"
    blur.inputs["Weight"].default_value = 1.0
    links.new(position.outputs["Position"], blur.inputs["Value"])
    links.new(group_input(nodes, {"Back Smooth"}).outputs["Back Smooth"], blur.inputs["Iterations"])
    difference = nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(blur.outputs["Value"], difference.inputs[0])
    links.new(position.outputs["Position"], difference.inputs[1])
    smooth_offset = nodes.new("ShaderNodeVectorMath")
    smooth_offset.operation = "SCALE"
    links.new(difference.outputs["Vector"], smooth_offset.inputs[0])
    links.new(weight, smooth_offset.inputs[3])
    smoothed = nodes.new("GeometryNodeSetPosition")
    links.new(extrude.outputs["Mesh"], smoothed.inputs["Geometry"])
    links.new(smooth_offset.outputs["Vector"], smoothed.inputs["Offset"])

    # Extruding against the normal leaves the rear leaf and wall facing inward.
    flipped = nodes.new("GeometryNodeFlipFaces")
    links.new(smoothed.outputs["Geometry"], flipped.inputs["Mesh"])
    rear = store_float_attribute(
        group, flipped.outputs["Mesh"], NORMAL_REDUCTION_ATTRIBUTE_NAME, 1.0,
    )
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(front.outputs["Geometry"], join.inputs["Geometry"])
    links.new(rear, join.inputs["Geometry"])
    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "ALL"
    links.new(weld_distance, merge.inputs["Distance"])
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])
    return merge.outputs["Geometry"]


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
    geometry = remove_boundary_triangles(group, geometry)
    boundary = edge_boundary_field(group.nodes, group.links)
    rim = evaluate_field(group, boundary, "FLOAT", "POINT")
    cut = evaluate_field(
        group, boolean_node(group, "AND", boundary, cut_vertex), "FLOAT", "POINT",
    )
    # Only the Depth Split cuts taper the profile; the outline keeps its thickness.
    geometry = taper_split_profile(group, geometry, cut)
    camera = build_surface_camera(
        group, _position_field(group, image), corner_camera, cut_vertex, split,
    )
    projection = project_depth_surface(
        group, geometry, camera, scale, controls.outputs["Reference Depth"], controls.outputs["Depth Scale"],
    )
    projection = smooth_cut_boundary(group, projection, cut_vertex, boundary=rim)
    # Clamped depth pixels can collapse adjacent outline samples after projection.
    edge = group.nodes.new("GeometryNodeInputMeshEdgeVertices")
    length = group.nodes.new("ShaderNodeVectorMath")
    length.operation = "DISTANCE"
    links.new(edge.outputs["Position 1"], length.inputs[0])
    links.new(edge.outputs["Position 2"], length.inputs[1])
    typical = group.nodes.new("GeometryNodeAttributeStatistic")
    typical.data_type, typical.domain = "FLOAT", "EDGE"
    links.new(projection, typical.inputs["Geometry"])
    links.new(length.outputs["Value"], typical.inputs["Attribute"])
    merge = group.nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "CONNECTED"
    links.new(projection, merge.inputs["Geometry"])
    links.new(_math(group, "MULTIPLY", typical.outputs["Mean"], 1e-6), merge.inputs["Distance"])
    projection = merge.outputs["Geometry"]
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
    projection = store_vector_attribute(
        group, projection, FRONT_NORMAL_ATTRIBUTE,
        build_normal_direction(group, controls, smoothed, average, weight),
    )
    solid = build_solid(
        group, projection, amount,
        read_vector_attribute(group, FRONT_NORMAL_ATTRIBUTE),
        is_shell, controls,
        _math(group, "MULTIPLY", typical.outputs["Mean"], SOLID_WELD_SCALE),
    )
    shaped = group.nodes.new("GeometryNodeSwitch")
    shaped.input_type = "GEOMETRY"
    links.new(has_thickness, shaped.inputs["Switch"])
    links.new(projection, shaped.inputs["False"])
    links.new(solid, shaped.inputs["True"])
    return remove_attribute_pattern(group, shaped.outputs[0], "_o_*")


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
    options = group.interface.new_panel(name='Options', default_closed=True)
    boundary_smooth = interface_socket(group, 'Boundary Smooth', 'INPUT', 'NodeSocketInt', options)
    boundary_smooth.default_value, boundary_smooth.min_value, boundary_smooth.max_value = 4, 0, 16
    boundary_smooth.description = 'Smooth geometry near the original outline and Depth Split edges. Zero disables boundary smoothing.'
    back_smooth = interface_socket(group, 'Back Smooth', 'INPUT', 'NodeSocketInt', options)
    back_smooth.default_value, back_smooth.min_value, back_smooth.max_value = 8, 0, 16
    back_smooth.description = 'Soften the rear surface where the balloon is thick. The effect follows Thickness and the balloon profile, so thin geometry and cut boundaries keep their positions.'
    float_input(group, 'Edge Turn', 2.0, minimum=-3.0, maximum=3.0, parent=options).description = 'Turn the outline direction: zero follows the smoothed normal, one reaches the island average normal, two mirrors the smoothed normal across it, and higher or negative values keep turning either way.'
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
