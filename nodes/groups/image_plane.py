"""Build the Image Plane Geometry Nodes group."""

import bpy
from mathutils import Matrix

from ..common.nodes import prepare_node_group
from ..common.material_slots import inherit_material_slots


IMAGE_PLANE_GROUP_NAME = "O Image Plane"


def new_socket(interface, name, in_out, socket_type, parent=None):
    socket = interface.new_socket(
        name=name,
        in_out=in_out,
        socket_type=socket_type,
        parent=parent,
    )
    if in_out == "INPUT" and hasattr(socket, "structure_type"):
        socket.structure_type = "SINGLE"
    return socket


def new_group_input(nodes, visible_names):
    node = nodes.new("NodeGroupInput")
    visible = set(visible_names)
    for output in node.outputs:
        output.hide = output.name not in visible
    return node


def build_dimension_fields(group):
    """Build independent source bounds for UV and mesh calculations."""
    sources = [
        group.nodes[name] for name in ("Bounding Box", "Vector Math", "Separate XYZ")
    ]
    for targets in (
        {"Math.011", "Math.013"},
        {"Grid", "Combine XYZ.001", "Vector Math.001"},
    ):
        copies = {source: group.nodes.new(source.bl_idname) for source in sources}
        copies[sources[1]].operation = "SUBTRACT"
        for link in list(group.links):
            if link.to_node in copies:
                source = copies.get(link.from_node, link.from_node)
                group.links.new(
                    source.outputs[link.from_socket.identifier],
                    copies[link.to_node].inputs[link.to_socket.identifier],
                )
            elif link.from_node in copies and link.to_node.name in targets:
                group.links.new(
                    copies[link.from_node].outputs[link.from_socket.identifier],
                    link.to_socket,
                )


def build_image_plane_group():
    group = bpy.data.node_groups.new(IMAGE_PLANE_GROUP_NAME, "GeometryNodeTree")
    group.is_modifier = True
    interface = group.interface
    geometry = new_socket(interface, "Geometry", "INPUT", "NodeSocketGeometry")
    geometry.structure_type = "SINGLE"
    subdivide = new_socket(interface, "Subdivide", "INPUT", "NodeSocketInt")
    subdivide.description = "Increase mesh density to represent finer shapes. Higher levels create more vertices and require more processing time."
    subdivide.default_value = 0
    subdivide.min_value = 0
    subdivide.max_value = 10
    thickness = new_socket(interface, "Thickness", "INPUT", "NodeSocketFloat")
    thickness.default_value = 0.0
    thickness.min_value = 0.0
    thickness.max_value = 10000.0
    thickness.subtype = "DISTANCE"
    new_socket(interface, "Geometry", "OUTPUT", "NodeSocketGeometry")

    nodes = group.nodes
    links = group.links
    geometry_input = new_group_input(nodes, {"Geometry"})
    subdivide_input = new_group_input(nodes, {"Subdivide"})
    thickness_input = new_group_input(nodes, {"Thickness"})
    output = nodes.new("NodeGroupOutput")

    bounds = nodes.new("GeometryNodeBoundBox")
    links.new(geometry_input.outputs["Geometry"], bounds.inputs["Geometry"])
    dimensions = nodes.new("ShaderNodeVectorMath")
    dimensions.operation = "SUBTRACT"
    links.new(bounds.outputs["Max"], dimensions.inputs[0])
    links.new(bounds.outputs["Min"], dimensions.inputs[1])
    separate_dimensions = nodes.new("ShaderNodeSeparateXYZ")
    links.new(dimensions.outputs["Vector"], separate_dimensions.inputs[0])

    short_segments = nodes.new("ShaderNodeMath")
    short_segments.operation = "POWER"
    short_segments.inputs[0].default_value = 2.0
    links.new(subdivide_input.outputs["Subdivide"], short_segments.inputs[1])

    vertex_counts = []
    for axis, other_axis in (("X", "Z"), ("Z", "X")):
        ratio = nodes.new("ShaderNodeMath")
        ratio.operation = "DIVIDE"
        links.new(separate_dimensions.outputs[axis], ratio.inputs[0])
        links.new(separate_dimensions.outputs[other_axis], ratio.inputs[1])
        at_least_one = nodes.new("ShaderNodeMath")
        at_least_one.operation = "MAXIMUM"
        at_least_one.inputs[1].default_value = 1.0
        links.new(ratio.outputs[0], at_least_one.inputs[0])
        scaled_segments = nodes.new("ShaderNodeMath")
        scaled_segments.operation = "MULTIPLY"
        links.new(short_segments.outputs[0], scaled_segments.inputs[0])
        links.new(at_least_one.outputs[0], scaled_segments.inputs[1])
        rounded_segments = nodes.new("ShaderNodeMath")
        rounded_segments.operation = "ROUND"
        links.new(scaled_segments.outputs[0], rounded_segments.inputs[0])
        vertices = nodes.new("ShaderNodeMath")
        vertices.operation = "ADD"
        vertices.inputs[1].default_value = 1.0
        links.new(rounded_segments.outputs[0], vertices.inputs[0])
        vertex_counts.append(vertices.outputs[0])

    grid = nodes.new("GeometryNodeMeshGrid")
    links.new(separate_dimensions.outputs["X"], grid.inputs["Size X"])
    links.new(separate_dimensions.outputs["Z"], grid.inputs["Size Y"])
    links.new(vertex_counts[0], grid.inputs["Vertices X"])
    links.new(vertex_counts[1], grid.inputs["Vertices Y"])
    position = nodes.new("GeometryNodeInputPosition")
    separate_position = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"], separate_position.inputs[0])
    uv_components = []
    for position_axis, dimension_axis in (("X", "X"), ("Y", "Z")):
        normalize = nodes.new("ShaderNodeMath")
        normalize.operation = "DIVIDE"
        links.new(separate_position.outputs[position_axis], normalize.inputs[0])
        links.new(separate_dimensions.outputs[dimension_axis], normalize.inputs[1])
        offset_uv = nodes.new("ShaderNodeMath")
        offset_uv.operation = "ADD"
        offset_uv.inputs[1].default_value = 0.5
        links.new(normalize.outputs[0], offset_uv.inputs[0])
        uv_components.append(offset_uv.outputs[0])
    uv_coordinates = nodes.new("ShaderNodeCombineXYZ")
    links.new(uv_components[0], uv_coordinates.inputs["X"])
    links.new(uv_components[1], uv_coordinates.inputs["Y"])

    cube_uv_components = []
    for position_axis, dimension_axis in (("X", "X"), ("Z", "Z")):
        normalize = nodes.new("ShaderNodeMath")
        normalize.operation = "DIVIDE"
        links.new(separate_position.outputs[position_axis], normalize.inputs[0])
        links.new(separate_dimensions.outputs[dimension_axis], normalize.inputs[1])
        offset_uv = nodes.new("ShaderNodeMath")
        offset_uv.operation = "ADD"
        offset_uv.inputs[1].default_value = 0.5
        links.new(normalize.outputs[0], offset_uv.inputs[0])
        cube_uv_components.append(offset_uv.outputs[0])
    cube_uv_coordinates = nodes.new("ShaderNodeCombineXYZ")
    links.new(cube_uv_components[0], cube_uv_coordinates.inputs["X"])
    links.new(cube_uv_components[1], cube_uv_coordinates.inputs["Y"])

    store_grid_uv = nodes.new("GeometryNodeStoreNamedAttribute")
    store_grid_uv.data_type = "FLOAT2"
    store_grid_uv.domain = "CORNER"
    store_grid_uv.inputs["Name"].default_value = "UVMap"
    links.new(grid.outputs["Mesh"], store_grid_uv.inputs["Geometry"])
    links.new(uv_coordinates.outputs["Vector"], store_grid_uv.inputs["Value"])

    rotate_grid = nodes.new("GeometryNodeTransform")
    rotate_grid.inputs["Rotation"].default_value = Matrix.Rotation(1.5707963267948966, 4, "X").to_euler()
    links.new(store_grid_uv.outputs["Geometry"], rotate_grid.inputs["Geometry"])

    center_sum = nodes.new("ShaderNodeVectorMath")
    center_sum.operation = "ADD"
    links.new(bounds.outputs["Min"], center_sum.inputs[0])
    links.new(bounds.outputs["Max"], center_sum.inputs[1])
    center = nodes.new("ShaderNodeVectorMath")
    center.operation = "SCALE"
    center.inputs[3].default_value = 0.5
    links.new(center_sum.outputs["Vector"], center.inputs[0])
    place_grid = nodes.new("GeometryNodeTransform")
    links.new(rotate_grid.outputs["Geometry"], place_grid.inputs["Geometry"])
    links.new(center.outputs["Vector"], place_grid.inputs["Translation"])

    cell_sizes = []
    for index, axis in enumerate(("X", "Z")):
        segments = nodes.new("ShaderNodeMath")
        segments.operation = "SUBTRACT"
        segments.inputs[1].default_value = 1.0
        links.new(vertex_counts[index], segments.inputs[0])
        cell_size = nodes.new("ShaderNodeMath")
        cell_size.operation = "DIVIDE"
        links.new(separate_dimensions.outputs[axis], cell_size.inputs[0])
        links.new(segments.outputs[0], cell_size.inputs[1])
        cell_sizes.append(cell_size.outputs[0])
    cell_area = nodes.new("ShaderNodeMath")
    cell_area.operation = "MULTIPLY"
    links.new(cell_sizes[0], cell_area.inputs[0])
    links.new(cell_sizes[1], cell_area.inputs[1])
    target_step = nodes.new("ShaderNodeMath")
    target_step.operation = "SQRT"
    links.new(cell_area.outputs[0], target_step.inputs[0])
    depth_ratio = nodes.new("ShaderNodeMath")
    depth_ratio.operation = "DIVIDE"
    links.new(thickness_input.outputs["Thickness"], depth_ratio.inputs[0])
    links.new(target_step.outputs[0], depth_ratio.inputs[1])
    rounded_depth = nodes.new("ShaderNodeMath")
    rounded_depth.operation = "ROUND"
    links.new(depth_ratio.outputs[0], rounded_depth.inputs[0])
    depth_segments = nodes.new("ShaderNodeMath")
    depth_segments.operation = "MAXIMUM"
    depth_segments.inputs[1].default_value = 3.0
    links.new(rounded_depth.outputs[0], depth_segments.inputs[0])
    depth_vertices = nodes.new("ShaderNodeMath")
    depth_vertices.operation = "ADD"
    depth_vertices.inputs[1].default_value = 1.0
    links.new(depth_segments.outputs[0], depth_vertices.inputs[0])

    cube_size = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate_dimensions.outputs["X"], cube_size.inputs["X"])
    links.new(thickness_input.outputs["Thickness"], cube_size.inputs["Y"])
    links.new(separate_dimensions.outputs["Z"], cube_size.inputs["Z"])
    cube = nodes.new("GeometryNodeMeshCube")
    links.new(cube_size.outputs["Vector"], cube.inputs["Size"])
    links.new(vertex_counts[0], cube.inputs["Vertices X"])
    links.new(depth_vertices.outputs[0], cube.inputs["Vertices Y"])
    links.new(vertex_counts[1], cube.inputs["Vertices Z"])
    store_cube_uv = nodes.new("GeometryNodeStoreNamedAttribute")
    store_cube_uv.data_type = "FLOAT2"
    store_cube_uv.domain = "CORNER"
    store_cube_uv.inputs["Name"].default_value = "UVMap"
    links.new(cube.outputs["Mesh"], store_cube_uv.inputs["Geometry"])
    links.new(cube_uv_coordinates.outputs["Vector"], store_cube_uv.inputs["Value"])
    place_cube = nodes.new("GeometryNodeTransform")
    links.new(store_cube_uv.outputs["Geometry"], place_cube.inputs["Geometry"])
    links.new(center.outputs["Vector"], place_cube.inputs["Translation"])
    has_thickness = nodes.new("FunctionNodeCompare")
    has_thickness.data_type = "FLOAT"
    has_thickness.operation = "GREATER_THAN"
    links.new(thickness_input.outputs["Thickness"], has_thickness.inputs[0])
    geometry_switch = nodes.new("GeometryNodeSwitch")
    geometry_switch.input_type = "GEOMETRY"
    links.new(has_thickness.outputs["Result"], geometry_switch.inputs["Switch"])
    links.new(place_grid.outputs["Geometry"], geometry_switch.inputs["False"])
    links.new(place_cube.outputs["Geometry"], geometry_switch.inputs["True"])

    geometry = inherit_material_slots(group, geometry_switch.outputs["Output"], geometry_input.outputs["Geometry"])
    links.new(geometry, output.inputs["Geometry"])

    group.color_tag = "GEOMETRY"
    group.description = (
        "Build an aspect-adaptive image plane and add optional centered thickness."
    )
    group.use_fake_user = True
    build_dimension_fields(group)
    prepare_node_group(group)
    return group
