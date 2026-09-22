"""Build shared boundary fields and pinned surface smoothing."""
from .nodes import evaluate_field, sample_field


UV_ATTRIBUTE = "UVMap"


def edge_boundary_field(nodes, links):
    """Report the points sitting on an open or loose boundary."""
    vertex_neighbors = nodes.new("GeometryNodeInputMeshVertexNeighbors")
    loose_vertex = nodes.new("FunctionNodeCompare")
    loose_vertex.data_type = "INT"
    loose_vertex.operation = "EQUAL"
    loose_vertex_a = next(
        socket for socket in loose_vertex.inputs if socket.identifier == "A_INT"
    )
    loose_vertex_b = next(
        socket for socket in loose_vertex.inputs if socket.identifier == "B_INT"
    )
    loose_vertex_b.default_value = 1
    links.new(vertex_neighbors.outputs["Vertex Count"], loose_vertex_a)

    edge_neighbors = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    boundary_edge = nodes.new("FunctionNodeCompare")
    boundary_edge.data_type = "INT"
    boundary_edge.operation = "EQUAL"
    boundary_edge_a = next(
        socket for socket in boundary_edge.inputs if socket.identifier == "A_INT"
    )
    boundary_edge_b = next(
        socket for socket in boundary_edge.inputs if socket.identifier == "B_INT"
    )
    boundary_edge_b.default_value = 1
    links.new(edge_neighbors.outputs["Face Count"], boundary_edge_a)
    edge_domain = nodes.new("GeometryNodeFieldOnDomain")
    edge_domain.data_type = "BOOLEAN"
    edge_domain.domain = "EDGE"
    links.new(boundary_edge.outputs["Result"], edge_domain.inputs["Value"])

    is_boundary = nodes.new("FunctionNodeBooleanMath")
    is_boundary.operation = "OR"
    links.new(edge_domain.outputs["Value"], is_boundary.inputs[0])
    links.new(loose_vertex.outputs["Result"], is_boundary.inputs[1])
    return is_boundary.outputs["Boolean"]


def _multiply(group, a, b):
    return _math(group, "MULTIPLY", a, b)


def _math(group, operation, *values):
    node = group.nodes.new("ShaderNodeMath")
    node.operation = operation
    for index, value in enumerate(values):
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            group.links.new(value, node.inputs[index])
    return node.outputs[0]


def _smooth_uv(group, geometry, influence, boundary_points=None):
    """Relax UVs as temporary point positions."""
    nodes, links = group.nodes, group.links
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = UV_ATTRIBUTE
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["Attribute"], axes.inputs[0])

    point_u = evaluate_field(group, axes.outputs["X"], "FLOAT", "POINT")
    point_v = evaluate_field(group, axes.outputs["Y"], "FLOAT", "POINT")
    uv_position = nodes.new("ShaderNodeCombineXYZ")
    links.new(point_u, uv_position.inputs["X"])
    links.new(point_v, uv_position.inputs["Z"])
    uv_geometry = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, uv_geometry.inputs["Geometry"])
    links.new(uv_position.outputs["Vector"], uv_geometry.inputs["Position"])
    position = nodes.new("GeometryNodeInputPosition")
    smooth = nodes.new("GeometryNodeBlurAttribute")
    smooth.data_type = "FLOAT_VECTOR"
    smooth.inputs["Iterations"].default_value = 1
    smooth.inputs["Weight"].default_value = 1.0
    links.new(position.outputs["Position"], smooth.inputs["Value"])
    target = sample_field(
        group, uv_geometry.outputs["Geometry"], smooth.outputs["Value"], "FLOAT_VECTOR",
    )
    if boundary_points is not None:
        choose = nodes.new("GeometryNodeSwitch")
        choose.input_type = "VECTOR"
        links.new(boundary_points, choose.inputs["Switch"])
        links.new(target, choose.inputs["False"])
        links.new(
            _boundary_target(group, uv_geometry.outputs["Geometry"], uv_geometry.outputs["Geometry"], boundary_points),
            choose.inputs["True"],
        )
        target = choose.outputs["Output"]
    target = evaluate_field(group, target, "FLOAT_VECTOR", "POINT")
    target_axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(target, target_axes.inputs[0])
    def mix(current, target):
        difference = _math(group, "SUBTRACT", target, current)
        return _math(group, "ADD", current, _math(group, "MULTIPLY", difference, influence))

    value = nodes.new("ShaderNodeCombineXYZ")
    links.new(mix(axes.outputs["X"], target_axes.outputs["X"]), value.inputs["X"])
    links.new(mix(axes.outputs["Y"], target_axes.outputs["Z"]), value.inputs["Y"])
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT2", "CORNER"
    store.inputs["Name"].default_value = UV_ATTRIBUTE
    links.new(geometry, store.inputs["Geometry"])
    links.new(value.outputs["Vector"], store.inputs["Value"])
    return store.outputs["Geometry"]


def _boundary_target(group, geometry, current, boundary_points):
    """Blur the boundary strip alone and sample it back onto every point."""
    nodes = group.nodes
    links = group.links
    boundary_geometry = nodes.new("GeometryNodeSeparateGeometry")
    boundary_geometry.domain = "POINT"
    links.new(current, boundary_geometry.inputs["Geometry"])
    links.new(boundary_points, boundary_geometry.inputs["Selection"])
    boundary_position = nodes.new("GeometryNodeInputPosition")
    smooth_boundary = nodes.new("GeometryNodeBlurAttribute")
    smooth_boundary.data_type = "FLOAT_VECTOR"
    smooth_boundary.inputs["Iterations"].default_value = 1
    smooth_boundary.inputs["Weight"].default_value = 0.5
    links.new(boundary_position.outputs["Position"], smooth_boundary.inputs["Value"])

    nearest_boundary = nodes.new("GeometryNodeSampleNearest")
    nearest_boundary.domain = "POINT"
    # Both boundary meshes keep the same compact index order: only positions change,
    # so the lookup can stay anchored on the untouched input geometry.
    source_boundary = nodes.new("GeometryNodeSeparateGeometry")
    source_boundary.domain = "POINT"
    links.new(geometry, source_boundary.inputs["Geometry"])
    links.new(boundary_points, source_boundary.inputs["Selection"])
    links.new(source_boundary.outputs["Selection"], nearest_boundary.inputs["Geometry"])
    fixed_position = sample_field(
        group, geometry, boundary_position.outputs["Position"], "FLOAT_VECTOR"
    )
    links.new(fixed_position, nearest_boundary.inputs["Sample Position"])

    sample_boundary = nodes.new("GeometryNodeSampleIndex")
    sample_boundary.data_type = "FLOAT_VECTOR"
    sample_boundary.domain = "POINT"
    sample_boundary.clamp = False
    links.new(boundary_geometry.outputs["Selection"], sample_boundary.inputs["Geometry"])
    links.new(smooth_boundary.outputs["Value"], sample_boundary.inputs["Value"])
    links.new(nearest_boundary.outputs["Index"], sample_boundary.inputs["Index"])
    return sample_boundary.outputs["Value"]


def pinned_smooth(
    group,
    geometry,
    iterations,
    region,
    weight=1.0,
    pin_boundary=True,
    pin_sharp=True,
):
    """Smooth positions and existing corner UVs inside an influence region.

    ``weight`` is the smoothing weight: each point moves that share of the way
    to the target every iteration, scaled further by the sharpness of the
    normal field and the influence region.
    ``pin_boundary`` sends boundary points to a boundary-only blur so an outline
    is never dragged inward. ``pin_sharp`` lowers the weight of creases through
    the sharpness of the normal field. Junction bands keep the sharpness weight
    without the boundary rule, where the influenced points are not a boundary.
    """
    nodes, links = group.nodes, group.links
    repeat_output = nodes.new("GeometryNodeRepeatOutput")
    repeat_input = nodes.new("GeometryNodeRepeatInput")
    repeat_input.pair_with_output(repeat_output)
    links.new(iterations, repeat_input.inputs["Iterations"])
    links.new(geometry, repeat_input.inputs["Geometry"])
    current = repeat_input.outputs["Geometry"]

    position = nodes.new("GeometryNodeInputPosition")
    smooth_all = nodes.new("GeometryNodeBlurAttribute")
    smooth_all.data_type = "FLOAT_VECTOR"
    smooth_all.inputs["Iterations"].default_value = 1
    smooth_all.inputs["Weight"].default_value = 1.0
    links.new(position.outputs["Position"], smooth_all.inputs["Value"])
    target = smooth_all.outputs["Value"]
    if pin_boundary:
        boundary_points = evaluate_field(
            group, edge_boundary_field(nodes, links), "BOOLEAN", "POINT"
        )
        choose = nodes.new("GeometryNodeSwitch")
        choose.input_type = "VECTOR"
        links.new(boundary_points, choose.inputs["Switch"])
        links.new(smooth_all.outputs["Value"], choose.inputs["False"])
        links.new(
            _boundary_target(group, geometry, current, boundary_points),
            choose.inputs["True"],
        )
        target = choose.outputs["Output"]

    if pin_sharp:
        normal = nodes.new("GeometryNodeInputNormal")
        smooth_normal = nodes.new("GeometryNodeBlurAttribute")
        smooth_normal.data_type = "FLOAT_VECTOR"
        smooth_normal.inputs["Iterations"].default_value = 10
        smooth_normal.inputs["Weight"].default_value = 1.0
        links.new(normal.outputs["Normal"], smooth_normal.inputs["Value"])
        coherence = nodes.new("ShaderNodeVectorMath")
        coherence.operation = "LENGTH"
        links.new(smooth_normal.outputs["Value"], coherence.inputs[0])
        weight = _multiply(group, weight, coherence.outputs["Value"])
    weight = _multiply(group, weight, region)

    difference = nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(target, difference.inputs[0])
    links.new(position.outputs["Position"], difference.inputs[1])
    offset = nodes.new("ShaderNodeVectorMath")
    offset.operation = "SCALE"
    links.new(difference.outputs[0], offset.inputs[0])
    links.new(weight, offset.inputs[3])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(current, set_position.inputs["Geometry"])
    links.new(offset.outputs[0], set_position.inputs["Offset"])
    smoothed = _smooth_uv(
        group, set_position.outputs["Geometry"], weight,
        boundary_points if pin_boundary else None,
    )
    links.new(smoothed, repeat_output.inputs["Geometry"])

    enabled = nodes.new("GeometryNodeSwitch")
    enabled.input_type = "GEOMETRY"
    links.new(iterations, enabled.inputs["Switch"])
    links.new(geometry, enabled.inputs["False"])
    links.new(repeat_output.outputs["Geometry"], enabled.inputs["True"])
    return enabled.outputs["Output"]
