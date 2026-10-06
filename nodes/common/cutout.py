"""Build geometry calculations shared by Cutout assets."""
from .nodes import math_node, store_int_attribute
from .smoothing import edge_boundary_field
from anyimage.operators.cutout_tool.shape import IMAGE_REGION_ATTRIBUTE_NAME


def _set_geometry_y(group, geometry, y_value):
    nodes = group.nodes
    links = group.links
    position = nodes.new("GeometryNodeInputPosition")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], separate.inputs["Vector"])
    target = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate.outputs["X"], target.inputs["X"])
    links.new(y_value, target.inputs["Y"])
    links.new(separate.outputs["Z"], target.inputs["Z"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, set_position.inputs["Geometry"])
    links.new(target.outputs["Vector"], set_position.inputs["Position"])
    return set_position.outputs["Geometry"]


def _side_to_midpoint(group, leaf, midpoint_y):
    """Extrude one leaf boundary to the shared side midpoint."""
    nodes, links = group.nodes, group.links
    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "EDGES"
    extrude.inputs["Offset"].default_value = (0.0, 1.0, 0.0)
    links.new(leaf, extrude.inputs["Mesh"])
    links.new(edge_boundary_field(nodes, links), extrude.inputs["Selection"])
    # Only the generated top ring moves to the midpoint; the source leaf is emitted separately.
    position = nodes.new("GeometryNodeInputPosition")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], separate.inputs["Vector"])
    target = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate.outputs["X"], target.inputs["X"])
    links.new(midpoint_y, target.inputs["Y"])
    links.new(separate.outputs["Z"], target.inputs["Z"])
    top_position = nodes.new("GeometryNodeSetPosition")
    links.new(extrude.outputs["Mesh"], top_position.inputs["Geometry"])
    links.new(extrude.outputs["Top"], top_position.inputs["Selection"])
    links.new(target.outputs["Vector"], top_position.inputs["Position"])
    sides = nodes.new("GeometryNodeSeparateGeometry")
    sides.domain = "FACE"
    links.new(top_position.outputs["Geometry"], sides.inputs["Geometry"])
    links.new(extrude.outputs["Side"], sides.inputs["Selection"])
    return sides.outputs["Selection"]


def _set_layer_y(group, geometry, front_y, back_y, *, build_sides=True):
    """Build separate Front and Rear side halves joined at one midpoint ring."""
    nodes, links = group.nodes, group.links
    front = _set_geometry_y(group, geometry, front_y)
    rear = _set_geometry_y(group, geometry, back_y)
    flip_rear = nodes.new("GeometryNodeFlipFaces")
    links.new(rear, flip_rear.inputs["Mesh"])
    rear = store_int_attribute(
        group, flip_rear.outputs["Mesh"], IMAGE_REGION_ATTRIBUTE_NAME, 1, domain="FACE",
    )
    join = nodes.new("GeometryNodeJoinGeometry")
    links.new(front, join.inputs["Geometry"])
    links.new(rear, join.inputs["Geometry"])
    if build_sides:
        midpoint = math_node(nodes, "ADD")
        links.new(front_y, midpoint.inputs[0])
        links.new(back_y, midpoint.inputs[1])
        midpoint_half = math_node(nodes, "MULTIPLY")
        midpoint_half.inputs[1].default_value = 0.5
        links.new(midpoint.outputs[0], midpoint_half.inputs[0])
        links.new(
            _side_to_midpoint(group, front, midpoint_half.outputs[0]),
            join.inputs["Geometry"],
        )
        links.new(
            _side_to_midpoint(group, rear, midpoint_half.outputs[0]),
            join.inputs["Geometry"],
        )
    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "ALL"
    merge.inputs["Distance"].default_value = 1e-6
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])
    return merge.outputs["Geometry"]


def _position_field(group, depth_image):
    nodes = group.nodes
    links = group.links
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    position_texture = nodes.new("GeometryNodeImageTexture")
    position_texture.interpolation = "Linear"
    position_texture.extension = "EXTEND"
    links.new(depth_image, position_texture.inputs["Image"])
    links.new(uv.outputs["Attribute"], position_texture.inputs["Vector"])
    return position_texture.outputs["Color"]


def _shade_output(group, geometry):
    shade = group.nodes.new("GeometryNodeSetShadeSmooth")
    shade.domain = "FACE"
    shade.inputs["Shade Smooth"].default_value = True
    output = group.nodes.new("NodeGroupOutput")
    group.links.new(geometry, shade.inputs["Geometry"])
    group.links.new(shade.outputs["Geometry"], output.inputs["Geometry"])
