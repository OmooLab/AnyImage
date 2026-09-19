"""Build a quad panorama with periodic sampling and radial depth separation."""

import math

import bpy

from ..common.depth_surface import (
    _math, split_depth_surface, build_surface_camera,
)
from ..common.nodes import (
    boolean_node, compare_node, float_input, group_input, interface_socket,
    prepare_node_group, evaluate_field, remove_attribute_pattern,
)
from ..common.material_slots import inherit_material_slots
from ..common.boundary_smoothing import smooth_boundary_depth, smooth_cut_boundary


def _quad_sphere(group, segments):
    nodes, links = group.nodes, group.links
    cube = nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (2, 2, 2)
    for axis in "XYZ":
        links.new(segments, cube.inputs[f"Vertices {axis}"])
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(nodes.new("GeometryNodeInputPosition").outputs[0], xyz.inputs[0])
    squares = {axis: _math(group, "MULTIPLY", xyz.outputs[axis], xyz.outputs[axis]) for axis in "XYZ"}
    combine = nodes.new("ShaderNodeCombineXYZ")
    for axis, a, b in (("X", "Y", "Z"), ("Y", "Z", "X"), ("Z", "X", "Y")):
        half = _math(group, "DIVIDE", _math(group, "ADD", squares[a], squares[b]), 2)
        third = _math(group, "DIVIDE", _math(group, "MULTIPLY", squares[a], squares[b]), 3)
        root = _math(group, "SQRT", _math(group, "ADD", _math(group, "SUBTRACT", 1, half), third))
        links.new(_math(group, "MULTIPLY", xyz.outputs[axis], root), combine.inputs[axis])
    position = nodes.new("GeometryNodeSetPosition")
    links.new(cube.outputs["Mesh"], position.inputs["Geometry"])
    links.new(combine.outputs[0], position.inputs["Position"])
    return position.outputs["Geometry"]


def build_image_depth_panorama_group():
    group = bpy.data.node_groups.new("O Image Depth Panorama", "GeometryNodeTree")
    group.is_modifier = group.use_fake_user = True
    interface_socket(group, "Geometry", "INPUT", "NodeSocketGeometry")
    subdivide = interface_socket(group, "Subdivide", "INPUT", "NodeSocketInt")
    subdivide.description = "Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time."
    subdivide.default_value, subdivide.min_value, subdivide.max_value = 8, 0, 8
    dome = float_input(group, "Dome Radius", 50, minimum=1, maximum=100, subtype="DISTANCE")
    dome.description = "Radius of the sphere kept at Depth Scale 0, and where mask areas below Mask Threshold land."
    float_input(group, "Depth Scale", 1, maximum=1, subtype="FACTOR").description = "Blend between a sphere at zero and the estimated depth surface at one."
    float_input(group, "Depth Split", 0.1, maximum=1, subtype="FACTOR").description = "Split the mesh where depth changes abruptly. Scaled by Depth Scale: a flat projection stays whole, higher values detect smaller depth jumps."
    valid_only = interface_socket(group, "Depth Mask", "INPUT", "NodeSocketBool")
    valid_only.default_value = True
    valid_only.description = "Remove mesh areas marked invalid by the depth mask; with the mask off, they rest on the dome sphere."
    options = group.interface.new_panel("Options", default_closed=True)
    boundary_smooth = interface_socket(group, "Boundary Smooth", "INPUT", "NodeSocketInt", options)
    boundary_smooth.default_value, boundary_smooth.min_value, boundary_smooth.max_value = 2, 0, 16
    boundary_smooth.description = "Smooth depth and geometry near cut edges on the panorama surface. Zero disables boundary smoothing."
    float_input(group, "Mask Threshold", 0.9, maximum=0.99, subtype="FACTOR", parent=options).description = "Set the minimum depth mask value treated as valid. Higher values exclude more partially valid boundary areas."
    data = group.interface.new_panel("Data", default_closed=True)
    interface_socket(group, "Depth Image", "INPUT", "NodeSocketImage", data).hide_in_modifier = True
    interface_socket(group, "Geometry", "OUTPUT", "NodeSocketGeometry")
    nodes, links = group.nodes, group.links

    def uv(direction):
        normalize = nodes.new("ShaderNodeVectorMath")
        normalize.operation = "NORMALIZE"
        links.new(direction, normalize.inputs[0])
        xyz = nodes.new("ShaderNodeSeparateXYZ")
        links.new(normalize.outputs[0], xyz.inputs[0])
        longitude = _math(group, "DIVIDE", _math(group, "ARCTAN2", xyz.outputs["Y"], xyz.outputs["X"]), 2 * math.pi)
        z = _math(group, "MAXIMUM", -1, _math(group, "MINIMUM", 1, xyz.outputs["Z"]))
        latitude = _math(group, "SUBTRACT", 1, _math(group, "DIVIDE", _math(group, "ARCCOSINE", z), math.pi))
        return longitude, latitude, xyz.outputs["Z"]

    def combine(u, v):
        node = nodes.new("ShaderNodeCombineXYZ")
        links.new(u, node.inputs["X"])
        links.new(v, node.inputs["Y"])
        return node.outputs[0]

    def texture(coordinates, interpolation):
        inputs = group_input(nodes, {"Depth Image"})
        info = nodes.new("GeometryNodeImageInfo")
        links.new(inputs.outputs["Depth Image"], info.inputs["Image"])
        axes = nodes.new("ShaderNodeSeparateXYZ")
        links.new(coordinates, axes.inputs[0])
        half_pixel = _math(group, "DIVIDE", 0.5, info.outputs["Height"])
        v = _math(group, "MAXIMUM", half_pixel,
                  _math(group, "MINIMUM", axes.outputs["Y"], _math(group, "SUBTRACT", 1, half_pixel)))
        node = nodes.new("GeometryNodeImageTexture")
        node.interpolation, node.extension = interpolation, "REPEAT"
        links.new(inputs.outputs["Depth Image"], node.inputs["Image"])
        links.new(combine(axes.outputs["X"], v), node.inputs["Vector"])
        return node.outputs["Color"]

    def depth(coordinates):
        linear, nearest = texture(coordinates, "Linear"), texture(coordinates, "Closest")
        alphas = []
        for color in (linear, nearest):
            separate = nodes.new("FunctionNodeSeparateColor")
            links.new(color, separate.inputs["Color"])
            alphas.append(separate.outputs["Alpha"])
        choose = nodes.new("GeometryNodeSwitch")
        choose.input_type = "RGBA"
        links.new(compare_node(group, "LESS_THAN", alphas[0],
                               _math(group, "SUBTRACT", alphas[1], 1e-6)), choose.inputs["Switch"])
        links.new(linear, choose.inputs["False"])
        links.new(nearest, choose.inputs["True"])
        return choose.outputs[0], alphas[1]

    inputs = group_input(nodes, {"Subdivide"})
    sphere = _quad_sphere(group, _math(group, "ADD", _math(group, "POWER", 2, inputs.outputs["Subdivide"]), 1))
    position = nodes.new("GeometryNodeInputPosition").outputs[0]
    longitude, latitude, z = uv(position)
    coordinates = evaluate_field(group, combine(longitude, latitude), "FLOAT_VECTOR", "POINT")
    face = nodes.new("GeometryNodeFieldOnDomain")
    face.data_type, face.domain = "FLOAT_VECTOR", "FACE"
    links.new(position, face.inputs["Value"])
    face_u, face_v, _ = uv(face.outputs["Value"])
    correction = _math(group, "ROUND", _math(group, "SUBTRACT", face_u, longitude))
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "FLOAT"
    links.new(compare_node(group, "GREATER_THAN", _math(group, "ABSOLUTE", z), 0.999999), choose.inputs["Switch"])
    links.new(_math(group, "ADD", longitude, correction), choose.inputs["False"])
    links.new(face_u, choose.inputs["True"])
    uv_map = nodes.new("GeometryNodeStoreNamedAttribute")
    uv_map.data_type, uv_map.domain = "FLOAT2", "CORNER"
    uv_map.inputs["Name"].default_value = "UVMap"
    links.new(sphere, uv_map.inputs["Geometry"])
    links.new(combine(choose.outputs[0], latitude), uv_map.inputs["Value"])
    pixel, _ = depth(coordinates)
    pixel = evaluate_field(group, pixel, "FLOAT_VECTOR", "POINT")
    # Both the mask and the depth of a face are read at its centre, like Depth Plane.
    face_camera, face_alpha = depth(combine(face_u, face_v))
    face_alpha = evaluate_field(group, face_alpha, "FLOAT", "FACE")
    threshold_input = group_input(nodes, {"Mask Threshold"})
    invalid = compare_node(group, "LESS_THAN", face_alpha, threshold_input.outputs["Mask Threshold"])
    protected = uv_map.outputs["Geometry"]
    separate = nodes.new("GeometryNodeSeparateGeometry")
    separate.domain = "FACE"
    links.new(protected, separate.inputs["Geometry"])
    links.new(invalid, separate.inputs["Selection"])
    controls = group_input(nodes, {"Depth Split", "Depth Scale"})
    strength = controls.outputs["Depth Split"]
    radial = nodes.new("ShaderNodeSeparateXYZ")
    links.new(face_camera, radial.inputs[0])
    geometry, corner_camera, cut_vertex = split_depth_surface(
        group, separate.outputs["Inverted"], face_camera, strength, 1.0, controls.outputs["Depth Scale"],
        face_distance=radial.outputs["X"], face_center=face.outputs["Value"],
    )
    distance = build_surface_camera(group, pixel, corner_camera, cut_vertex, strength)
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(distance, axes.inputs[0])
    distance = smooth_boundary_depth(group, axes.outputs["X"])
    dome_radius = group_input(nodes, {"Dome Radius"}).outputs["Dome Radius"]
    radius = _math(
        group, "ADD", dome_radius,
        _math(group, "MULTIPLY", controls.outputs["Depth Scale"],
              _math(group, "SUBTRACT", distance, dome_radius)),
    )
    radial = nodes.new("ShaderNodeVectorMath")
    radial.operation = "SCALE"
    links.new(position, radial.inputs[0])
    links.new(radius, radial.inputs[3])
    deform = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, deform.inputs["Geometry"])
    links.new(radial.outputs[0], deform.inputs["Position"])
    geometry = remove_attribute_pattern(group, deform.outputs[0], "_o_*")
    geometry = smooth_cut_boundary(group, geometry, cut_vertex, outline_scale=1.0)
    # The excluded faces rest on the dome sphere and relax along their own boundary.
    domed = nodes.new("ShaderNodeVectorMath")
    domed.operation = "SCALE"
    links.new(position, domed.inputs[0])
    links.new(dome_radius, domed.inputs[3])
    resting = nodes.new("GeometryNodeSetPosition")
    links.new(separate.outputs["Selection"], resting.inputs["Geometry"])
    links.new(domed.outputs[0], resting.inputs["Position"])
    resting = smooth_cut_boundary(group, resting.outputs["Geometry"], outline_scale=1.0)
    joined = nodes.new("GeometryNodeJoinGeometry")
    links.new(geometry, joined.inputs["Geometry"])
    links.new(resting, joined.inputs["Geometry"])
    # A flat projection without the mask is the dome sphere alone: no split, no seam.
    dome_sphere = nodes.new("GeometryNodeSetPosition")
    links.new(protected, dome_sphere.inputs["Geometry"])
    links.new(domed.outputs[0], dome_sphere.inputs["Position"])
    cull_controls = group_input(nodes, {"Depth Mask"})
    dome_only = boolean_node(
        group,
        "AND",
        boolean_node(group, "NOT", compare_node(group, "GREATER_THAN", controls.outputs["Depth Scale"], 0.0)),
        boolean_node(group, "NOT", cull_controls.outputs["Depth Mask"]),
    )
    unmasked = nodes.new("GeometryNodeSwitch")
    unmasked.input_type = "GEOMETRY"
    links.new(dome_only, unmasked.inputs["Switch"])
    links.new(joined.outputs["Geometry"], unmasked.inputs["False"])
    links.new(dome_sphere.outputs["Geometry"], unmasked.inputs["True"])
    cull = nodes.new("GeometryNodeSwitch")
    cull.input_type = "GEOMETRY"
    links.new(cull_controls.outputs["Depth Mask"], cull.inputs["Switch"])
    links.new(unmasked.outputs["Output"], cull.inputs["False"])
    links.new(geometry, cull.inputs["True"])
    flip = nodes.new("GeometryNodeFlipFaces")
    links.new(cull.outputs["Output"], flip.inputs["Mesh"])
    smooth = nodes.new("GeometryNodeSetShadeSmooth")
    smooth.domain = "FACE"
    smooth.inputs["Shade Smooth"].default_value = True
    links.new(flip.outputs["Mesh"], smooth.inputs["Geometry"])
    geometry = inherit_material_slots(group, smooth.outputs[0], group_input(nodes, {"Geometry"}).outputs["Geometry"])
    output = nodes.new("NodeGroupOutput")
    links.new(geometry, output.inputs["Geometry"])
    prepare_node_group(group)
    return group
