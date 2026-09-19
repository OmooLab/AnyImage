"""Build the Relief Plane Geometry Nodes group."""

import bpy

from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.nodes import group_input as _group_input, interface_socket as _interface_socket
from ..common.nodes import store_float_attribute
from ..common.nodes import compare_node, prepare_node_group, vector_input
from ..common.reference_plane import reference_plane_depth
from ..common.boundary_smoothing import boundary_influence


RELIEF_PLANE_NODE_GROUP_NAME = "O Image Relief Plane"


def _math(nodes, operation):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    return node


def build_image_relief_plane_group(image_plane_group):
    group = bpy.data.node_groups.get(RELIEF_PLANE_NODE_GROUP_NAME)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(
        RELIEF_PLANE_NODE_GROUP_NAME,
        "GeometryNodeTree",
    )
    group.is_modifier = True
    geometry = _interface_socket(group, "Geometry", "INPUT", "NodeSocketGeometry")
    geometry.structure_type = "SINGLE"
    subdivide = _interface_socket(group, "Subdivide", "INPUT", "NodeSocketInt")
    subdivide.description = "Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time."
    subdivide.default_value = 6
    subdivide.min_value = 0
    subdivide.max_value = 10
    thickness = _interface_socket(group, "Thickness", "INPUT", "NodeSocketFloat")
    thickness.default_value = 0.0
    thickness.min_value = 0.0
    thickness.subtype = "DISTANCE"
    thickness.description = "Set the thickness of the flat base beneath the relief."
    vector_input(group, "Depth Direction", (0, 0, 1), subtype="DIRECTION").description = "Set the direction used to orient the reference depth plane."
    depth_offset = _interface_socket(group, "Depth Offset", "INPUT", "NodeSocketFloat")
    depth_offset.default_value = 0.0
    depth_offset.min_value = -10.0
    depth_offset.max_value = 10.0
    depth_offset.subtype = "DISTANCE"
    depth_offset.description = "Correct the reference depth before direction and scale are applied."
    depth_scale = _interface_socket(group, "Depth Scale", "INPUT", "NodeSocketFloat")
    depth_scale.default_value = 0.5
    depth_scale.min_value = 0.0
    depth_scale.max_value = 2.0
    valid_only = _interface_socket(group, "Depth Mask", "INPUT", "NodeSocketBool")
    valid_only.description = "Treat depth-mask-invalid areas as zero depth instead of deleting them."
    valid_only.default_value = True
    options = group.interface.new_panel(name="Options", default_closed=True)
    validity_threshold = _interface_socket(group, "Mask Threshold", "INPUT", "NodeSocketFloat", options)
    validity_threshold.description = "Set the minimum depth mask value treated as valid."
    validity_threshold.default_value = 0.9
    validity_threshold.min_value, validity_threshold.max_value = 0.0, 0.99
    validity_threshold.subtype = "FACTOR"
    base_plane_depth = _interface_socket(
        group,
        "Reference Depth",
        "INPUT",
        "NodeSocketFloat",
        parent=options,
    )
    base_plane_depth.default_value = 1.0
    base_plane_depth.min_value = 0.0
    base_plane_depth.subtype = "DISTANCE"
    data = group.interface.new_panel(name="Data", default_closed=True)
    uniform_scale = _interface_socket(
        group,
        "Uniform Scale",
        "INPUT",
        "NodeSocketFloat",
        parent=data,
    )
    uniform_scale.default_value = 1.0
    uniform_scale.min_value = 0.0
    uniform_scale.hide_in_modifier = True
    depth_image = _interface_socket(
        group,
        "Depth Image",
        "INPUT",
        "NodeSocketImage",
        parent=data,
    )
    depth_image.hide_in_modifier = True
    _interface_socket(group, "Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = group.nodes
    links = group.links
    geometry_input = _group_input(
        nodes,
        {"Geometry", "Subdivide"},
    )
    shape_input = _group_input(
        nodes,
        {"Thickness", "Depth Direction", "Depth Offset", "Depth Scale"},
    )
    image_input = _group_input(
        nodes,
        {"Depth Image", "Uniform Scale", "Depth Mask", "Mask Threshold"},
    )
    group_output = nodes.new("NodeGroupOutput")
    image_plane = nodes.new("GeometryNodeGroup")
    image_plane.node_tree = image_plane_group
    links.new(geometry_input.outputs["Geometry"], image_plane.inputs["Geometry"])
    links.new(geometry_input.outputs["Subdivide"], image_plane.inputs["Subdivide"])
    links.new(shape_input.outputs["Thickness"], image_plane.inputs["Thickness"])

    positive_half = _math(nodes, "MULTIPLY")
    positive_half.inputs[1].default_value = 0.5
    links.new(shape_input.outputs["Thickness"], positive_half.inputs[0])
    translation = nodes.new("ShaderNodeCombineXYZ")
    links.new(positive_half.outputs[0], translation.inputs["Y"])
    place_block = nodes.new("GeometryNodeTransform")
    links.new(image_plane.outputs["Geometry"], place_block.inputs["Geometry"])
    links.new(translation.outputs["Vector"], place_block.inputs["Translation"])

    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    texture = nodes.new("GeometryNodeImageTexture")
    texture.interpolation = "Linear"
    texture.extension = "EXTEND"
    links.new(image_input.outputs["Depth Image"], texture.inputs["Image"])
    links.new(uv.outputs["Attribute"], texture.inputs["Vector"])
    depth_components = nodes.new("ShaderNodeSeparateXYZ")
    links.new(texture.outputs["Color"], depth_components.inputs["Vector"])
    invalid = nodes.new("FunctionNodeCompare")
    invalid.data_type, invalid.operation = "FLOAT", "LESS_THAN"
    links.new(texture.outputs["Alpha"], invalid.inputs["A"])
    links.new(image_input.outputs["Mask Threshold"], invalid.inputs["B"])
    mask_enabled = image_input.outputs["Depth Mask"]
    valid_mask = nodes.new("GeometryNodeSwitch")
    valid_mask.input_type = "FLOAT"
    valid_mask.inputs["False"].default_value = 1.0
    links.new(invalid.outputs["Result"], valid_mask.inputs["Switch"])
    mask_switch = nodes.new("GeometryNodeSwitch")
    mask_switch.input_type = "FLOAT"
    mask_switch.inputs["False"].default_value = 1.0
    links.new(mask_enabled, mask_switch.inputs["Switch"])
    links.new(valid_mask.outputs[0], mask_switch.inputs["True"])
    metric_depth = _math(nodes, "MULTIPLY")
    links.new(depth_components.outputs["Z"], metric_depth.inputs[0])
    links.new(image_input.outputs["Uniform Scale"], metric_depth.inputs[1])
    relative_depth = _math(nodes, "SUBTRACT")
    reference_input = _group_input(nodes, {"Reference Depth"})
    corrected_reference = _math(nodes, "ADD")
    links.new(reference_input.outputs["Reference Depth"], corrected_reference.inputs[0])
    links.new(shape_input.outputs["Depth Offset"], corrected_reference.inputs[1])
    plane_depth = reference_plane_depth(
        group, shape_input.outputs["Depth Direction"], corrected_reference.outputs[0],
    )
    links.new(metric_depth.outputs[0], relative_depth.inputs[0])
    links.new(plane_depth, relative_depth.inputs[1])
    full_offset = _math(nodes, "MULTIPLY")
    links.new(relative_depth.outputs[0], full_offset.inputs[0])
    links.new(shape_input.outputs["Depth Scale"], full_offset.inputs[1])
    masked_full_offset = _math(nodes, "MULTIPLY")
    links.new(full_offset.outputs[0], masked_full_offset.inputs[0])
    links.new(mask_switch.outputs[0], masked_full_offset.inputs[1])

    has_thickness = compare_node(group, "GREATER_THAN", shape_input.outputs["Thickness"], 1e-6)
    safe_offset = _math(nodes, "MINIMUM")
    safe_offset.inputs[1].default_value = 0.0
    links.new(masked_full_offset.outputs[0], safe_offset.inputs[0])
    edge_influence = boundary_influence(group, protected=False)
    edge_clamped = nodes.new("ShaderNodeClamp")
    edge_clamped.inputs["Min"].default_value = 0.0
    edge_clamped.inputs["Max"].default_value = 1.0
    links.new(edge_influence, edge_clamped.inputs["Value"])
    geometry_weight = _math(nodes, "SUBTRACT")
    geometry_weight.inputs[0].default_value = 1.0
    links.new(edge_clamped.outputs[0], geometry_weight.inputs[1])
    smooth_safe_offset = _math(nodes, "MULTIPLY")
    links.new(safe_offset.outputs[0], smooth_safe_offset.inputs[0])
    links.new(geometry_weight.outputs[0], smooth_safe_offset.inputs[1])

    position = nodes.new("GeometryNodeInputPosition")
    position_components = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], position_components.inputs["Vector"])
    layer_ratio = _math(nodes, "DIVIDE")
    links.new(position_components.outputs["Y"], layer_ratio.inputs[0])
    links.new(shape_input.outputs["Thickness"], layer_ratio.inputs[1])
    nonnegative_ratio = _math(nodes, "MAXIMUM")
    nonnegative_ratio.inputs[1].default_value = 0.0
    links.new(layer_ratio.outputs[0], nonnegative_ratio.inputs[0])
    clamped_ratio = _math(nodes, "MINIMUM")
    clamped_ratio.inputs[1].default_value = 1.0
    links.new(nonnegative_ratio.outputs[0], clamped_ratio.inputs[0])
    one_minus_ratio = _math(nodes, "SUBTRACT")
    one_minus_ratio.inputs[0].default_value = 1.0
    links.new(clamped_ratio.outputs[0], one_minus_ratio.inputs[1])
    layer_weight = nodes.new("GeometryNodeSwitch")
    layer_weight.input_type = "FLOAT"
    layer_weight.inputs["False"].default_value = 1.0
    links.new(has_thickness, layer_weight.inputs["Switch"])
    links.new(one_minus_ratio.outputs[0], layer_weight.inputs["True"])

    weighted_offset = _math(nodes, "MULTIPLY")
    links.new(smooth_safe_offset.outputs[0], weighted_offset.inputs[0])
    links.new(layer_weight.outputs["Output"], weighted_offset.inputs[1])
    displacement = nodes.new("ShaderNodeCombineXYZ")
    links.new(weighted_offset.outputs[0], displacement.inputs["Y"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(place_block.outputs["Geometry"], set_position.inputs["Geometry"])
    links.new(displacement.outputs["Vector"], set_position.inputs["Offset"])
    shade_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    shade_smooth.domain = "FACE"
    shade_smooth.inputs["Shade Smooth"].default_value = True
    links.new(set_position.outputs["Geometry"], shade_smooth.inputs["Geometry"])
    normal_reduction = _math(nodes, "SUBTRACT")
    normal_reduction.inputs[0].default_value = 1.0
    scaled_depth = _math(nodes, "MULTIPLY")
    links.new(shape_input.outputs["Depth Scale"], scaled_depth.inputs[0])
    links.new(geometry_weight.outputs[0], scaled_depth.inputs[1])
    links.new(scaled_depth.outputs[0], normal_reduction.inputs[1])
    output_geometry = store_float_attribute(
        group, shade_smooth.outputs["Geometry"], NORMAL_REDUCTION_ATTRIBUTE_NAME,
        normal_reduction.outputs[0],
    )
    links.new(output_geometry, group_output.inputs["Geometry"])
    group.color_tag = "GEOMETRY"
    group.description = (
        "Build a fixed-base image relief."
    )
    group.use_fake_user = True
    prepare_node_group(group)
    return group
