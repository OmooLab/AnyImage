"""Build shared boundary fields and pinned surface smoothing."""
from .nodes import (
    evaluate_field,
    read_float_attribute,
    remove_attribute_pattern,
    store_boolean_attribute,
    store_float_attribute,
)


UV_ATTRIBUTE = "UVMap"
UV_SMOOTH_ITERATIONS = 4
PINNED_BOUNDARY_ATTRIBUTE = "_o_pinned_smooth_boundary"
PINNED_NORMALIZATION_ATTRIBUTE = "_o_pinned_smooth_normalization"
PINNED_REGION_POINT_ATTRIBUTE = "_o_pinned_smooth_region_point"
PINNED_REGION_CORNER_ATTRIBUTE = "_o_pinned_smooth_region_corner"


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


def _blur(group, value, data_type, *, weight=1.0):
    node = group.nodes.new("GeometryNodeBlurAttribute")
    node.data_type = data_type
    node.inputs["Iterations"].default_value = 1
    node.inputs["Weight"].default_value = weight
    group.links.new(value, node.inputs["Value"])
    return node.outputs["Value"]


def _boundary_target(group, value, boundary_points, normalization):
    """Normalize a masked blur to include only boundary neighbors."""
    masked = group.nodes.new("ShaderNodeVectorMath")
    masked.operation = "SCALE"
    group.links.new(value, masked.inputs[0])
    group.links.new(boundary_points, masked.inputs[3])
    numerator = _blur(group, masked.outputs[0], "FLOAT_VECTOR", weight=0.5)
    target = group.nodes.new("ShaderNodeVectorMath")
    target.operation = "SCALE"
    group.links.new(numerator, target.inputs[0])
    group.links.new(
        _math(group, "DIVIDE", 1.0, _math(group, "MAXIMUM", normalization, 1e-8)),
        target.inputs[3],
    )
    return target.outputs[0]


def _smooth_uv(
    group,
    geometry,
    influence,
    boundary_points=None,
    boundary_normalization=None,
):
    """Relax point-domain UV values and store them on face corners."""
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
    links.new(point_v, uv_position.inputs["Y"])
    target = _blur(group, uv_position.outputs["Vector"], "FLOAT_VECTOR")
    if boundary_points is not None:
        choose = nodes.new("GeometryNodeSwitch")
        choose.input_type = "VECTOR"
        links.new(boundary_points, choose.inputs["Switch"])
        links.new(target, choose.inputs["False"])
        links.new(
            _boundary_target(
                group,
                uv_position.outputs["Vector"],
                boundary_points,
                boundary_normalization,
            ),
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
    links.new(mix(axes.outputs["Y"], target_axes.outputs["Y"]), value.inputs["Y"])
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT2", "CORNER"
    store.inputs["Name"].default_value = UV_ATTRIBUTE
    links.new(geometry, store.inputs["Geometry"])
    links.new(value.outputs["Vector"], store.inputs["Value"])
    return store.outputs["Geometry"]


def pinned_smooth(
    group,
    geometry,
    iterations,
    region,
    weight=1.0,
    pin_boundary=True,
    pin_sharp=True,
    cache_region=False,
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
    prepared = geometry
    position_region = region
    uv_region = region
    if cache_region:
        prepared = store_float_attribute(
            group,
            prepared,
            PINNED_REGION_POINT_ATTRIBUTE,
            region,
            domain="POINT",
        )
        corner_prepared = store_float_attribute(
            group,
            prepared,
            PINNED_REGION_CORNER_ATTRIBUTE,
            region,
            domain="CORNER",
        )
        prepared = corner_prepared
        position_region = read_float_attribute(
            group, PINNED_REGION_POINT_ATTRIBUTE,
        )
        uv_region = read_float_attribute(
            group, PINNED_REGION_CORNER_ATTRIBUTE,
        )
    boundary_points = None
    boundary_normalization = None
    if pin_boundary:
        prepared, boundary_points = store_boolean_attribute(
            group,
            prepared,
            PINNED_BOUNDARY_ATTRIBUTE,
            evaluate_field(
                group, edge_boundary_field(nodes, links), "BOOLEAN", "POINT",
            ),
        )
        prepared = store_float_attribute(
            group,
            prepared,
            PINNED_NORMALIZATION_ATTRIBUTE,
            _blur(group, boundary_points, "FLOAT", weight=0.5),
        )
        boundary_normalization = read_float_attribute(
            group, PINNED_NORMALIZATION_ATTRIBUTE,
        )

    repeat_output = nodes.new("GeometryNodeRepeatOutput")
    repeat_input = nodes.new("GeometryNodeRepeatInput")
    repeat_input.pair_with_output(repeat_output)
    links.new(iterations, repeat_input.inputs["Iterations"])
    links.new(prepared, repeat_input.inputs["Geometry"])
    current = repeat_input.outputs["Geometry"]

    position = nodes.new("GeometryNodeInputPosition")
    target = _blur(group, position.outputs["Position"], "FLOAT_VECTOR")
    if pin_boundary:
        choose = nodes.new("GeometryNodeSwitch")
        choose.input_type = "VECTOR"
        links.new(boundary_points, choose.inputs["Switch"])
        links.new(target, choose.inputs["False"])
        links.new(
            _boundary_target(
                group, position.outputs["Position"], boundary_points, boundary_normalization,
            ),
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
    position_weight = _multiply(group, weight, position_region)
    uv_weight = (
        _multiply(group, weight, uv_region)
        if cache_region else position_weight
    )

    difference = nodes.new("ShaderNodeVectorMath")
    difference.operation = "SUBTRACT"
    links.new(target, difference.inputs[0])
    links.new(position.outputs["Position"], difference.inputs[1])
    offset = nodes.new("ShaderNodeVectorMath")
    offset.operation = "SCALE"
    links.new(difference.outputs[0], offset.inputs[0])
    links.new(position_weight, offset.inputs[3])
    smoothed_uv = _smooth_uv(
        group,
        current,
        uv_weight,
        boundary_points if pin_boundary else None,
        boundary_normalization,
    )
    uv_iteration = nodes.new("FunctionNodeCompare")
    uv_iteration.data_type = "INT"
    uv_iteration.operation = "LESS_THAN"
    uv_iteration_a = next(
        socket for socket in uv_iteration.inputs if socket.identifier == "A_INT"
    )
    uv_iteration_b = next(
        socket for socket in uv_iteration.inputs if socket.identifier == "B_INT"
    )
    uv_iteration_b.default_value = UV_SMOOTH_ITERATIONS
    links.new(repeat_input.outputs["Iteration"], uv_iteration_a)
    uv_enabled = nodes.new("GeometryNodeSwitch")
    uv_enabled.input_type = "GEOMETRY"
    links.new(uv_iteration.outputs["Result"], uv_enabled.inputs["Switch"])
    links.new(current, uv_enabled.inputs["False"])
    links.new(smoothed_uv, uv_enabled.inputs["True"])
    set_position = nodes.new("GeometryNodeSetPosition")
    links.new(uv_enabled.outputs["Output"], set_position.inputs["Geometry"])
    links.new(offset.outputs[0], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], repeat_output.inputs["Geometry"])

    enabled = nodes.new("GeometryNodeSwitch")
    enabled.input_type = "GEOMETRY"
    links.new(iterations, enabled.inputs["Switch"])
    links.new(geometry, enabled.inputs["False"])
    result = repeat_output.outputs["Geometry"]
    if pin_boundary or cache_region:
        result = remove_attribute_pattern(group, result, "_o_pinned_smooth_*")
    links.new(result, enabled.inputs["True"])
    return enabled.outputs["Output"]
