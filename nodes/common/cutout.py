"""Build geometry calculations shared by Cutout assets."""
from .nodes import compare_node, math_node
from anyimage.operators.cutout_tool.shape import BALLOON_ATTRIBUTE_NAME


def _profile_field(group, geometry):
    nodes = group.nodes
    links = group.links
    profile = nodes.new("GeometryNodeInputNamedAttribute")
    profile.data_type = "FLOAT"
    profile.inputs["Name"].default_value = BALLOON_ATTRIBUTE_NAME
    profile_max = nodes.new("GeometryNodeAttributeStatistic")
    profile_max.data_type = "FLOAT"
    profile_max.domain = "POINT"
    links.new(geometry, profile_max.inputs["Geometry"])
    links.new(profile.outputs["Attribute"], profile_max.inputs["Attribute"])
    safe_max = math_node(nodes, "MAXIMUM")
    safe_max.inputs[1].default_value = 1e-6
    links.new(profile_max.outputs["Max"], safe_max.inputs[0])
    normalized = math_node(nodes, "DIVIDE")
    links.new(profile.outputs["Attribute"], normalized.inputs[0])
    links.new(safe_max.outputs[0], normalized.inputs[1])
    smooth = nodes.new("ShaderNodeMapRange")
    smooth.data_type = "FLOAT"
    smooth.interpolation_type = "SMOOTHERSTEP"
    smooth.clamp = True
    smooth.inputs["From Min"].default_value = 0.0
    smooth.inputs["From Max"].default_value = 1.0
    smooth.inputs["To Min"].default_value = 0.0
    smooth.inputs["To Max"].default_value = 1.0
    links.new(normalized.outputs[0], smooth.inputs["Value"])
    return profile.outputs["Attribute"], smooth.outputs["Result"]


def _extrude_layers(group, geometry):
    node = group.nodes.new("GeometryNodeExtrudeMesh")
    node.mode = "FACES"
    node.inputs["Individual"].default_value = False
    node.inputs["Offset"].default_value = (0.0, 1.0, 0.0)
    # Keep distinct front and back vertices before overriding their Y positions.
    node.inputs["Offset Scale"].default_value = 1.0
    group.links.new(geometry, node.inputs["Mesh"])
    return node


def _offset_geometry_y(group, geometry, y_value):
    nodes = group.nodes
    links = group.links
    offset = nodes.new("ShaderNodeCombineXYZ")
    links.new(y_value, offset.inputs["Y"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, set_position.inputs["Geometry"])
    links.new(offset.outputs["Vector"], set_position.inputs["Offset"])
    return set_position.outputs["Geometry"]


def _set_layer_y(group, geometry, extrude, front_y, back_y):
    nodes = group.nodes
    links = group.links
    choose_y = nodes.new("GeometryNodeSwitch")
    choose_y.input_type = "FLOAT"
    links.new(extrude.outputs["Top"], choose_y.inputs["Switch"])
    links.new(front_y, choose_y.inputs["False"])
    links.new(back_y, choose_y.inputs["True"])
    position = nodes.new("GeometryNodeInputPosition")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], separate.inputs["Vector"])
    combine = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate.outputs["X"], combine.inputs["X"])
    links.new(choose_y.outputs["Output"], combine.inputs["Y"])
    links.new(separate.outputs["Z"], combine.inputs["Z"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(extrude.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(combine.outputs["Vector"], set_position.inputs["Position"])

    side = nodes.new("GeometryNodeSeparateGeometry")
    side.domain = "FACE"
    links.new(set_position.outputs["Geometry"], side.inputs["Geometry"])
    links.new(extrude.outputs["Side"], side.inputs["Selection"])
    flip_side = nodes.new("GeometryNodeFlipFaces")
    links.new(side.outputs["Selection"], flip_side.inputs["Mesh"])
    front = _offset_geometry_y(
        group, geometry, front_y
    )
    back = _offset_geometry_y(
        group, geometry, back_y
    )
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


def _remove_zero_thickness(
    group,
    zero_geometry,
    shaped_geometry,
    thickness,
):
    nodes = group.nodes
    links = group.links
    zero = compare_node(group, "LESS_THAN", thickness, 1e-6)
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(zero, choose.inputs["Switch"])
    links.new(shaped_geometry, choose.inputs["False"])
    links.new(zero_geometry, choose.inputs["True"])
    return choose.outputs["Output"]


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
