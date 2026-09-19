"""Apply boundary-preserving smoothing within a narrow cut-edge band."""

from .nodes import boolean_node, compare_node, evaluate_field, group_input
from .depth_surface import _math
from .smoothing import edge_boundary_field, pinned_smooth


def _gated(group, value, blocked, *, default):
    """Return the value unless the blocked control is true."""
    if blocked is False:
        return value
    node = group.nodes.new("GeometryNodeSwitch")
    node.input_type = "FLOAT"
    node.inputs["True"].default_value = default
    if isinstance(blocked, bool):
        node.inputs["Switch"].default_value = blocked
    else:
        group.links.new(blocked, node.inputs["Switch"])
    group.links.new(value, node.inputs["False"])
    return node.outputs[0]


def boundary_influence(group, protected=False, *, boundary=None):
    """Fade a boundary field through two rings while excluding protected points."""
    nodes, links = group.nodes, group.links
    if boundary is None:
        boundary = edge_boundary_field(nodes, links)
    boundary = evaluate_field(group, boundary, "FLOAT", "POINT")
    cut = _gated(group, boundary, protected, default=0.0)
    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT"
    blur.inputs["Iterations"].default_value = 2
    blur.inputs["Weight"].default_value = 1
    links.new(cut, blur.inputs["Value"])
    mixed = _math(group, "MAXIMUM", cut, blur.outputs["Value"])
    return _gated(group, mixed, protected, default=0.0)


def smooth_boundary_depth(group, depth, protected=False):
    """Blur point depth on the current mesh and apply it only in the edge band."""
    nodes, links = group.nodes, group.links
    depth = evaluate_field(group, depth, "FLOAT", "POINT")
    iterations = group_input(nodes, {"Boundary Smooth"}).outputs["Boundary Smooth"]
    influence = boundary_influence(group, protected)
    blur = nodes.new("GeometryNodeBlurAttribute")
    blur.data_type = "FLOAT"
    blur.inputs["Weight"].default_value = 0.5
    links.new(depth, blur.inputs["Value"])
    links.new(iterations, blur.inputs["Iterations"])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "FLOAT"
    links.new(influence, mix.inputs[0])
    links.new(depth, mix.inputs[2])
    links.new(blur.outputs["Value"], mix.inputs[3])
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "FLOAT"
    links.new(influence, choose.inputs["Switch"])
    links.new(depth, choose.inputs["False"])
    links.new(mix.outputs[0], choose.inputs["True"])
    enabled = nodes.new("GeometryNodeSwitch")
    enabled.input_type = "FLOAT"
    links.new(iterations, enabled.inputs["Switch"])
    links.new(depth, enabled.inputs["False"])
    links.new(choose.outputs[0], enabled.inputs["True"])
    return enabled.outputs[0]


def smooth_boundary_camera(group, camera, protected=False):
    """Reconstruct blurred camera depth along each unchanged projection ray."""
    nodes, links = group.nodes, group.links
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(camera, axes.inputs[0])
    depth = axes.outputs["Z"]
    smoothed = smooth_boundary_depth(group, depth, protected)
    return reconstruct_camera_depth(group, camera, depth, smoothed)


def reconstruct_camera_depth(group, camera, depth, smoothed):
    """Move each valid camera point along its original projection ray."""
    nodes, links = group.nodes, group.links
    changed = compare_node(group, "GREATER_THAN", _math(group, "ABSOLUTE", _math(group, "SUBTRACT", smoothed, depth)), 0)
    enabled = boolean_node(group, "AND", changed, compare_node(group, "GREATER_THAN", depth, 1e-8))
    projected = nodes.new("ShaderNodeVectorMath")
    projected.operation = "SCALE"
    links.new(camera, projected.inputs[0])
    links.new(_math(group, "DIVIDE", smoothed, depth), projected.inputs[3])
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "VECTOR"
    links.new(enabled, choose.inputs["Switch"])
    links.new(camera, choose.inputs["False"])
    links.new(projected.outputs[0], choose.inputs["True"])
    return choose.outputs[0]


def cut_boundary_influence(group, split_boundary, protected=False, *, outline_scale=0.1, boundary=None):
    """Give split edges full influence and outline edges a configured share."""
    nodes, links = group.nodes, group.links
    if boundary is None:
        boundary = evaluate_field(group, edge_boundary_field(nodes, links), "FLOAT", "POINT")
    split = _gated(group, boundary, boolean_node(group, "NOT", split_boundary), default=0.0)
    outline = _math(group, "MAXIMUM", _math(group, "SUBTRACT", boundary, split), 0)
    split_influence = boundary_influence(group, protected, boundary=split)
    outline_influence = _math(
        group, "MULTIPLY", boundary_influence(group, protected, boundary=outline), outline_scale,
    )
    return _math(group, "MAXIMUM", split_influence, outline_influence)


def smooth_cut_boundary(group, geometry, split_boundary=False, *, protected=False, outline_scale=0.1, boundary=None):
    """Move boundary vertices toward the pinned position through split and outline influence."""
    influence = cut_boundary_influence(
        group, split_boundary, protected, outline_scale=outline_scale, boundary=boundary,
    )
    # The support band depends on topology, which stays unchanged in the loop.
    iterations = group_input(group.nodes, {"Boundary Smooth"}).outputs["Boundary Smooth"]
    return pinned_smooth(group, geometry, iterations, influence)
