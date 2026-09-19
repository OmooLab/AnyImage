"""Build the direction-adjusted reference depth field."""
from .nodes import math_node
from .direction import legacy_direction_to_canonical


def reference_plane_depth(group, direction, reference_depth):
    nodes = group.nodes
    links = group.links
    normal = nodes.new("ShaderNodeVectorMath")
    normal.operation = "NORMALIZE"
    links.new(direction, normal.inputs[0])
    remapped = legacy_direction_to_canonical(group, normal.outputs["Vector"])
    normal_components = nodes.new("ShaderNodeSeparateXYZ")
    links.new(remapped, normal_components.inputs["Vector"])
    position = nodes.new("GeometryNodeInputPosition")
    position_components = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], position_components.inputs["Vector"])
    x_term = math_node(nodes, "MULTIPLY")
    links.new(position_components.outputs["X"], x_term.inputs[0])
    links.new(normal_components.outputs["X"], x_term.inputs[1])
    z_term = math_node(nodes, "MULTIPLY")
    links.new(position_components.outputs["Z"], z_term.inputs[0])
    links.new(normal_components.outputs["Z"], z_term.inputs[1])
    point_dot = math_node(nodes, "ADD")
    links.new(x_term.outputs[0], point_dot.inputs[0])
    links.new(z_term.outputs[0], point_dot.inputs[1])
    divide = math_node(nodes, "DIVIDE")
    links.new(point_dot.outputs[0], divide.inputs[0])
    links.new(normal_components.outputs["Y"], divide.inputs[1])
    plane = math_node(nodes, "ADD")
    links.new(reference_depth, plane.inputs[0])
    links.new(divide.outputs[0], plane.inputs[1])
    return plane.outputs[0]
