"""Build O Image Cutout."""
import bpy
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import (
    interface_socket, group_input, compare_node, math_node, float_input,
    menu_switch, read_float_attribute, store_float_attribute, prepare_node_group,
)
from ..common.cutout import _extrude_layers, _offset_geometry_y, _set_layer_y, _shade_output


NODE_GROUP_NAME = "O Image Cutout"


def _set_segmented_layer_y(
    group,
    geometry,
    front_z,
    back_z,
    thickness,
):
    nodes = group.nodes
    links = group.links

    edge_vertices = nodes.new("GeometryNodeInputMeshEdgeVertices")
    edge_length = nodes.new("ShaderNodeVectorMath")
    edge_length.operation = "DISTANCE"
    links.new(edge_vertices.outputs["Position 1"], edge_length.inputs[0])
    links.new(edge_vertices.outputs["Position 2"], edge_length.inputs[1])
    edge_neighbors = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    boundary = compare_node(group, "EQUAL", edge_neighbors.outputs["Face Count"], 1, data_type="INT")
    statistics = nodes.new("GeometryNodeAttributeStatistic")
    statistics.data_type = "FLOAT"
    statistics.domain = "EDGE"
    links.new(geometry, statistics.inputs["Geometry"])
    links.new(boundary, statistics.inputs["Selection"])
    links.new(edge_length.outputs["Value"], statistics.inputs["Attribute"])
    safe_edge = math_node(nodes, "MAXIMUM")
    safe_edge.inputs[1].default_value = 1e-6
    links.new(statistics.outputs["Median"], safe_edge.inputs[0])
    segment_ratio = math_node(nodes, "DIVIDE")
    links.new(thickness, segment_ratio.inputs[0])
    links.new(safe_edge.outputs[0], segment_ratio.inputs[1])
    segment_count = nodes.new("FunctionNodeFloatToInt")
    segment_count.rounding_mode = "CEILING"
    links.new(segment_ratio.outputs[0], segment_count.inputs["Float"])
    at_least_one = nodes.new("FunctionNodeIntegerMath")
    at_least_one.operation = "MAXIMUM"
    at_least_one.inputs[1].default_value = 1
    links.new(segment_count.outputs["Integer"], at_least_one.inputs[0])
    segment_limit = nodes.new("FunctionNodeIntegerMath")
    segment_limit.operation = "MINIMUM"
    segment_limit.inputs[1].default_value = 128
    links.new(at_least_one.outputs[0], segment_limit.inputs[0])
    step = math_node(nodes, "DIVIDE")
    links.new(thickness, step.inputs[0])
    links.new(segment_limit.outputs[0], step.inputs[1])

    front = _offset_geometry_y(group, geometry, front_z)
    repeat_output = nodes.new("GeometryNodeRepeatOutput")
    repeat_input = nodes.new("GeometryNodeRepeatInput")
    repeat_input.pair_with_output(repeat_output)
    repeat_output.repeat_items.new("GEOMETRY", "Geometry")
    repeat_output.repeat_items.new("GEOMETRY", "Sides")
    links.new(segment_limit.outputs[0], repeat_input.inputs["Iterations"])
    links.new(geometry, repeat_input.inputs["Geometry"])
    negative_step = math_node(nodes, "MULTIPLY")
    negative_step.inputs[1].default_value = -1.0
    links.new(step.outputs[0], negative_step.inputs[0])
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    extrude.inputs["Selection"].default_value = True
    extrude.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
    links.new(negative_step.outputs[0], extrude.inputs["Offset Scale"])
    links.new(repeat_input.outputs["Geometry"], extrude.inputs["Mesh"])
    split_extrude = nodes.new("GeometryNodeSeparateGeometry")
    split_extrude.domain = "FACE"
    links.new(extrude.outputs["Mesh"], split_extrude.inputs["Geometry"])
    links.new(extrude.outputs["Side"], split_extrude.inputs["Selection"])
    join_sides = nodes.new("GeometryNodeJoinGeometry")
    links.new(repeat_input.outputs["Sides"], join_sides.inputs["Geometry"])
    links.new(split_extrude.outputs["Selection"], join_sides.inputs["Geometry"])
    links.new(split_extrude.outputs["Inverted"], repeat_output.inputs["Geometry"])
    links.new(join_sides.outputs["Geometry"], repeat_output.inputs["Sides"])

    positioned_side = _offset_geometry_y(
        group,
        repeat_output.outputs["Sides"],
        front_z,
    )
    flip_side = nodes.new("GeometryNodeFlipFaces")
    links.new(positioned_side, flip_side.inputs["Mesh"])

    back = _offset_geometry_y(group, geometry, back_z)
    flip_back = nodes.new("GeometryNodeFlipFaces")
    links.new(back, flip_back.inputs["Mesh"])
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(front, join.inputs["Geometry"])
    links.new(flip_back.outputs["Mesh"], join.inputs["Geometry"])
    links.new(flip_side.outputs["Mesh"], join.inputs["Geometry"])
    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "ALL"
    merge.inputs["Distance"].default_value = 1e-6
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])
    return merge.outputs["Geometry"]


def _build_shell(group, geometry, thickness):
    nodes = group.nodes
    links = group.links
    zero = compare_node(group, "LESS_THAN", thickness, 1e-6)
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(zero, choose.inputs["Switch"])
    links.new(geometry, choose.inputs["True"])
    front = math_node(nodes, "MULTIPLY")
    front.inputs[1].default_value = 0.0
    links.new(thickness, front.inputs[0])
    back = math_node(nodes, "MULTIPLY")
    back.inputs[1].default_value = 1.0
    links.new(thickness, back.inputs[0])
    shaped = _set_segmented_layer_y(
        group,
        geometry,
        front.outputs[0],
        back.outputs[0],
        thickness,
    )
    links.new(shaped, choose.inputs["False"])
    return choose.outputs[0]


def _build_balloon(group, geometry, thickness):
    nodes = group.nodes
    links = group.links
    zero = compare_node(group, "LESS_THAN", thickness, 1e-6)
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(zero, choose.inputs["Switch"])
    links.new(geometry, choose.inputs["True"])
    profile = read_float_attribute(group, 'o_balloon')
    front_scale = math_node(nodes, "MULTIPLY")
    links.new(profile, front_scale.inputs[0])
    links.new(thickness, front_scale.inputs[1])
    negative_front = math_node(nodes, "MULTIPLY")
    negative_front.inputs[1].default_value = -1.0
    links.new(front_scale.outputs[0], negative_front.inputs[0])
    extrude = _extrude_layers(group, geometry)
    shaped = _set_layer_y(
        group,
        geometry,
        extrude,
        negative_front.outputs[0],
        front_scale.outputs[0],
    )
    links.new(shaped, choose.inputs["False"])
    return choose.outputs[0]


def build_image_cutout_group():
    name = NODE_GROUP_NAME
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    group.is_modifier, group.use_fake_user = (True, True)
    group.color_tag = 'GEOMETRY'
    interface_socket(group, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    interface_socket(group, 'Mode', 'INPUT', 'NodeSocketMenu')
    float_input(group, 'Thickness', 1.0, maximum=2.0).description = 'Control how much the surface bulges in Balloon mode. Zero removes the bulge.'
    float_input(group, 'Shell Thickness', 0.0, maximum=1.0, subtype='DISTANCE').description = 'Add thickness behind the original surface while keeping the front surface in place.'
    interface_socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    controls = group_input(group.nodes, set())
    balloon = _build_balloon(group, controls.outputs['Geometry'], controls.outputs['Thickness'])
    shell = _build_shell(group, controls.outputs['Geometry'], controls.outputs['Shell Thickness'])
    choose = menu_switch(group, 'Mode', ('Balloon', 'Shell'), 'GEOMETRY')
    group.links.new(balloon, choose.inputs['Balloon'])
    group.links.new(shell, choose.inputs['Shell'])
    geometry = choose.outputs[0]
    profile = read_float_attribute(group, 'o_balloon')
    amount = group_input(group.nodes, {'Thickness'})
    enabled = compare_node(group, 'GREATER_THAN', amount.outputs['Thickness'], 1e-6)
    inflated = group.nodes.new('GeometryNodeSwitch')
    inflated.input_type = 'FLOAT'
    inflated.inputs['False'].default_value = 1
    group.links.new(enabled, inflated.inputs['Switch'])
    group.links.new(profile, inflated.inputs['True'])
    mode = menu_switch(group, 'Mode', ('Balloon', 'Shell'), 'FLOAT')
    mode.inputs['Shell'].default_value = 1
    group.links.new(inflated.outputs[0], mode.inputs['Balloon'])
    scale = mode.outputs[0]
    reduction = math_node(group.nodes, 'SUBTRACT')
    reduction.inputs[0].default_value = 1.0
    group.links.new(scale, reduction.inputs[1])
    geometry = store_float_attribute(group, geometry, NORMAL_REDUCTION_ATTRIBUTE_NAME, reduction.outputs[0])
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
