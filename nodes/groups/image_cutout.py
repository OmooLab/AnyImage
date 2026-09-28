"""Build O Image Cutout."""
import bpy
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import (
    interface_socket, group_input, compare_node, math_node, float_input,
    menu_switch, read_float_attribute, store_float_attribute, prepare_node_group,
)
from ..common.cutout import _set_layer_y, _shade_output


NODE_GROUP_NAME = "O Image Cutout"


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
    shaped = _set_layer_y(group, geometry, front.outputs[0], back.outputs[0])
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
    shaped = _set_layer_y(
        group,
        geometry,
        negative_front.outputs[0],
        front_scale.outputs[0],
        build_sides=False,
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
