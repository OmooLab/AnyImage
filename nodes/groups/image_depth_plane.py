"""Build the camera-projected Depth Plane Geometry Nodes group."""

import bpy

from ..common.validity import delete_invalid_faces

from ..common.nodes import group_input as _group_input, interface_socket as _interface_socket
from ..common.nodes import compare_node, prepare_node_group, float_input, evaluate_field
from ..common.boundary_smoothing import smooth_boundary_camera, smooth_cut_boundary
from ..common.depth_surface import (
    _math, project_depth_surface, thicken_depth_surface,
    split_depth_surface, sample_face_camera, build_surface_camera,
)

DEPTH_PLANE_NODE_GROUP_NAME = "O Image Depth Plane"


def build_image_depth_plane_group(image_plane_group):
    group = bpy.data.node_groups.get(DEPTH_PLANE_NODE_GROUP_NAME)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(
        DEPTH_PLANE_NODE_GROUP_NAME,
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
    thickness.description = "Add shell thickness inward from the depth surface. Zero keeps a single surface."
    depth_scale = _interface_socket(group, "Depth Scale", "INPUT", "NodeSocketFloat")
    depth_scale.default_value = 1.0
    depth_scale.min_value = 0.0
    depth_scale.max_value = 2.0
    float_input(group, "Depth Split", 0.1, maximum=1, subtype="FACTOR").description = "Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps."
    valid_only = _interface_socket(group, "Depth Mask", "INPUT", "NodeSocketBool")
    valid_only.description = "Remove mesh areas marked invalid by the depth mask."
    valid_only.default_value = True
    options = group.interface.new_panel(name="Options", default_closed=True)
    boundary_smooth = _interface_socket(group, "Boundary Smooth", "INPUT", "NodeSocketInt", parent=options)
    boundary_smooth.default_value, boundary_smooth.min_value, boundary_smooth.max_value = 4, 0, 16
    boundary_smooth.description = "Smooth depth and geometry near cut edges while preserving the original image border. Zero disables boundary smoothing."
    validity_threshold = _interface_socket(group, "Mask Threshold", "INPUT", "NodeSocketFloat", parent=options)
    validity_threshold.description = "Set the minimum depth mask value treated as valid. Higher values exclude more partially valid boundary areas."
    validity_threshold.default_value = 0.9
    validity_threshold.min_value, validity_threshold.max_value = 0.0, 0.99
    validity_threshold.subtype = "FACTOR"
    float_input(group, "Reference Depth", 1.0, subtype="DISTANCE", parent=options)
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

    nodes, links = group.nodes, group.links
    controls = _group_input(nodes, {"Geometry", "Subdivide"})
    plane = nodes.new("GeometryNodeGroup")
    plane.node_tree = image_plane_group
    plane.inputs["Thickness"].default_value = 0
    links.new(controls.outputs["Geometry"], plane.inputs["Geometry"])
    links.new(controls.outputs["Subdivide"], plane.inputs["Subdivide"])
    texture_input = _group_input(nodes, {"Depth Image"})
    scale_input = _group_input(nodes, {"Uniform Scale"})
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    texture = nodes.new("GeometryNodeImageTexture")
    texture.interpolation, texture.extension = "Linear", "EXTEND"
    links.new(uv.outputs["Attribute"], texture.inputs["Vector"])
    links.new(texture_input.outputs["Depth Image"], texture.inputs["Image"])
    threshold_input = _group_input(nodes, {"Mask Threshold"})
    channels = nodes.new("FunctionNodeSeparateColor")
    channels.mode = "RGB"
    links.new(texture.outputs["Color"], channels.inputs["Color"])
    invalid = nodes.new("FunctionNodeCompare")
    invalid.data_type, invalid.operation = "FLOAT", "LESS_THAN"
    links.new(channels.outputs["Alpha"], invalid.inputs["A"])
    links.new(threshold_input.outputs["Mask Threshold"], invalid.inputs["B"])
    # Image Plane's normalized UV rectangle retains its original outline after cuts.
    uv_axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["Attribute"], uv_axes.inputs[0])
    u, v = uv_axes.outputs["X"], uv_axes.outputs["Y"]
    margin = _math(group, "MINIMUM", _math(group, "MINIMUM", u, v),
                   _math(group, "MINIMUM", _math(group, "SUBTRACT", 1, u), _math(group, "SUBTRACT", 1, v)))
    original_boundary = evaluate_field(group, compare_node(group, "LESS_THAN", margin, 1e-6), "BOOLEAN", "POINT")
    protected = plane.outputs["Geometry"]
    culled = delete_invalid_faces(group, protected, invalid.outputs["Result"])
    cull_controls = _group_input(nodes, {"Depth Mask"})
    cull = nodes.new("GeometryNodeSwitch")
    cull.input_type = "GEOMETRY"
    links.new(cull_controls.outputs["Depth Mask"], cull.inputs["Switch"])
    links.new(culled, cull.inputs["True"])
    links.new(protected, cull.inputs["False"])
    split_input = _group_input(nodes, {"Depth Split", "Depth Scale"})
    reference_input = _group_input(nodes, {"Reference Depth"})
    geometry, corner_camera, cut_vertex = split_depth_surface(
        group, cull.outputs["Output"], sample_face_camera(group, texture_input.outputs["Depth Image"]),
        split_input.outputs["Depth Split"], reference_input.outputs["Reference Depth"],
        split_input.outputs["Depth Scale"],
    )
    camera = build_surface_camera(
        group, texture.outputs["Color"], corner_camera, cut_vertex,
        split_input.outputs["Depth Split"],
    )
    depth_input = _group_input(nodes, {"Reference Depth", "Depth Scale"})
    camera = smooth_boundary_camera(group, camera, original_boundary)
    surface = project_depth_surface(
        group, geometry, camera,
        scale_input.outputs["Uniform Scale"], depth_input.outputs["Reference Depth"],
        depth_input.outputs["Depth Scale"],
    )
    surface = smooth_cut_boundary(
        group, surface, cut_vertex, protected=original_boundary, outline_scale=1.0,
    )
    shell_input = _group_input(nodes, {"Thickness"})
    shell = thicken_depth_surface(
        group, surface, shell_input.outputs["Thickness"],
        normal_smooth=100,
    )
    positive = compare_node(group, "GREATER_THAN", shell_input.outputs["Thickness"], 0)
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(positive, choose.inputs["Switch"])
    links.new(surface, choose.inputs["False"])
    links.new(shell["geometry"], choose.inputs["True"])
    smooth = nodes.new("GeometryNodeSetShadeSmooth")
    smooth.domain = "FACE"
    links.new(choose.outputs["Output"], smooth.inputs["Geometry"])
    output = nodes.new("NodeGroupOutput")
    links.new(smooth.outputs["Geometry"], output.inputs["Geometry"])
    group.color_tag = "GEOMETRY"
    group.description = "Build a camera-projected image shell."
    group.use_fake_user = True
    prepare_node_group(group)
    return group
