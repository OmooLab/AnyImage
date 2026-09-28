"""Build geometry calculations shared by Cutout assets."""
from .nodes import compare_node, math_node
from .smoothing import edge_boundary_field
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


def move_uv_to_lower_tile(group, geometry, selection=None):
    """Mirror Face Corner U and move V into the lower atlas tile."""
    nodes = group.nodes
    links = group.links
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    transform = nodes.new("ShaderNodeVectorMath")
    transform.operation = "MULTIPLY_ADD"
    transform.inputs[1].default_value = (-1.0, 1.0, 1.0)
    transform.inputs[2].default_value = (1.0, -0.5, 0.0)
    links.new(uv.outputs["Attribute"], transform.inputs[0])
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT2", "CORNER"
    store.inputs["Name"].default_value = "UVMap"
    links.new(geometry, store.inputs["Geometry"])
    if selection is not None:
        links.new(selection, store.inputs["Selection"])
    links.new(transform.outputs["Vector"], store.inputs["Value"])
    return store.outputs["Geometry"]


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
    rear = move_uv_to_lower_tile(group, flip_rear.outputs["Mesh"])
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
    sample_uv = source_depth_uv(group, depth_image, uv.outputs["Attribute"])
    position_texture = nodes.new("GeometryNodeImageTexture")
    position_texture.interpolation = "Linear"
    position_texture.extension = "EXTEND"
    links.new(depth_image, position_texture.inputs["Image"])
    links.new(sample_uv, position_texture.inputs["Vector"])
    return position_texture.outputs["Color"]


def source_depth_uv(group, image, uv):
    """Restore zero-to-one source UVs from the material Front tile."""
    nodes, links = group.nodes, group.links
    transform = nodes.new("ShaderNodeVectorMath")
    transform.operation = "MULTIPLY_ADD"
    transform.inputs[1].default_value = (1.0, 2.0, 1.0)
    transform.inputs[2].default_value = (0.0, -1.0, 0.0)
    links.new(uv, transform.inputs[0])
    image_info = nodes.new("GeometryNodeImageInfo")
    links.new(image, image_info.inputs["Image"])
    half_texel = math_node(nodes, "DIVIDE")
    half_texel.inputs[0].default_value = 0.5
    links.new(image_info.outputs["Height"], half_texel.inputs[1])
    maximum = math_node(nodes, "SUBTRACT")
    maximum.inputs[0].default_value = 1.0
    links.new(half_texel.outputs[0], maximum.inputs[1])
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(transform.outputs["Vector"], separate.inputs["Vector"])
    lower = math_node(nodes, "MAXIMUM")
    links.new(separate.outputs["Y"], lower.inputs[0])
    links.new(half_texel.outputs[0], lower.inputs[1])
    upper = math_node(nodes, "MINIMUM")
    links.new(lower.outputs[0], upper.inputs[0])
    links.new(maximum.outputs[0], upper.inputs[1])
    combine = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate.outputs["X"], combine.inputs["X"])
    links.new(upper.outputs[0], combine.inputs["Y"])
    links.new(separate.outputs["Z"], combine.inputs["Z"])
    return combine.outputs["Vector"]


def _shade_output(group, geometry):
    shade = group.nodes.new("GeometryNodeSetShadeSmooth")
    shade.domain = "FACE"
    shade.inputs["Shade Smooth"].default_value = True
    output = group.nodes.new("NodeGroupOutput")
    group.links.new(geometry, shade.inputs["Geometry"])
    group.links.new(shade.outputs["Geometry"], output.inputs["Geometry"])
