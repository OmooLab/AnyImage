"""Face separation and connected thickness for Depth Surface assets."""

from .nodes import (
    boolean_node, compare_node, evaluate_field, store_boolean_attribute,
    remove_attribute_pattern, sample_field,
)
from .smoothing import edge_boundary_field


CUT_ATTRIBUTE = "_o_depth_cut"
LIMIT_BOUNDARY_ATTRIBUTE = "_o_depth_limit_boundary"


def _math(group, operation, a, b=None):
    node = group.nodes.new("ShaderNodeMath")
    node.operation = operation
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            group.links.new(value, node.inputs[index])
    return node.outputs[0]


def _remove_strip_faces(group, geometry, *, triangles=False):
    """Delete boundary strips from one unchanged topology snapshot."""
    if triangles:
        return _remove_triangle_strip_faces(group, geometry)
    return _remove_quad_strip_faces(group, geometry)


def _remove_quad_strip_faces(group, geometry):
    """Delete boundary quad strips while preserving open boundary edges."""
    nodes, links = group.nodes, group.links

    def equals(value, count):
        return compare_node(group, "EQUAL", value, count, data_type="INT")

    boundaries = []
    for offset in range(4):
        index = nodes.new("GeometryNodeInputIndex")
        corners = nodes.new("GeometryNodeCornersOfFace")
        links.new(index.outputs[0], corners.inputs["Face Index"])
        corner = nodes.new("GeometryNodeOffsetCornerInFace")
        corner.inputs["Offset"].default_value = offset
        links.new(corners.outputs["Corner Index"], corner.inputs["Corner Index"])
        edge = nodes.new("GeometryNodeEdgesOfCorner")
        links.new(corner.outputs["Corner Index"], edge.inputs["Corner Index"])
        sample = nodes.new("GeometryNodeFieldAtIndex")
        sample.data_type, sample.domain = "INT", "EDGE"
        links.new(edge.outputs["Next Edge Index"], sample.inputs["Index"])
        neighbors = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
        links.new(neighbors.outputs["Face Count"], sample.inputs["Value"])
        boundaries.append(equals(sample.outputs["Value"], 1))
    opposite = boolean_node(
        group, "OR",
        boolean_node(group, "AND", boundaries[0], boundaries[2]),
        boolean_node(group, "AND", boundaries[1], boundaries[3]),
    )
    face = nodes.new("GeometryNodeInputMeshFaceNeighbors")
    selected = boolean_node(group, "AND", equals(face.outputs["Vertex Count"], 4), opposite)
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain, delete.mode = "FACE", "ALL"
    links.new(geometry, delete.inputs["Geometry"])
    links.new(selected, delete.inputs["Selection"])
    return delete.outputs["Geometry"]


def _remove_triangle_strip_faces(group, geometry):
    """Delete symmetric triangle strip pairs and all-boundary ears."""
    nodes, links = group.nodes, group.links

    def equals(value, count):
        return compare_node(group, "EQUAL", value, count, data_type="INT")

    def sample(value, index, domain, data_type="INT"):
        node = nodes.new("GeometryNodeFieldAtIndex")
        node.data_type, node.domain = data_type, domain
        links.new(value, node.inputs["Value"])
        links.new(index, node.inputs["Index"])
        return node.outputs["Value"]

    def offset_corner(corner, offset):
        node = nodes.new("GeometryNodeOffsetCornerInFace")
        links.new(corner, node.inputs["Corner Index"])
        node.inputs["Offset"].default_value = offset
        return node.outputs["Corner Index"]

    def vertex(corner):
        node = nodes.new("GeometryNodeVertexOfCorner")
        links.new(corner, node.inputs["Corner Index"])
        return node.outputs["Vertex Index"]

    def boundary(corner):
        edge = nodes.new("GeometryNodeEdgesOfCorner")
        links.new(corner, edge.inputs["Corner Index"])
        count = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
        return equals(sample(count.outputs["Face Count"], edge.outputs["Next Edge Index"], "EDGE"), 1)

    edge_index = nodes.new("GeometryNodeInputIndex")
    sides = []
    for side in (0, 1):
        corners = nodes.new("GeometryNodeCornersOfEdge")
        links.new(edge_index.outputs[0], corners.inputs["Edge Index"])
        corners.inputs["Sort Index"].default_value = side
        corner = corners.outputs["Corner Index"]
        face_index = nodes.new("GeometryNodeFaceOfCorner")
        links.new(corner, face_index.inputs["Corner Index"])
        face_size = nodes.new("GeometryNodeInputMeshFaceNeighbors")
        triangle = equals(sample(face_size.outputs["Vertex Count"], face_index.outputs["Face Index"], "FACE"), 3)
        end, tip = offset_corner(corner, 1), offset_corner(corner, 2)
        sides.append((triangle, vertex(corner), vertex(tip), boundary(end), boundary(tip)))
    a, b = sides
    same_direction = equals(a[1], b[1])
    same_order = boolean_node(
        group, "OR",
        boolean_node(group, "AND", a[3], b[3]),
        boolean_node(group, "AND", a[4], b[4]),
    )
    reverse_order = boolean_node(
        group, "OR",
        boolean_node(group, "AND", a[3], b[4]),
        boolean_node(group, "AND", a[4], b[3]),
    )
    pair = boolean_node(
        group, "OR",
        boolean_node(group, "AND", same_direction, reverse_order),
        boolean_node(group, "AND", boolean_node(group, "NOT", same_direction), same_order),
    )
    neighbors = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    for condition in (
        equals(neighbors.outputs["Face Count"], 2),
        a[0],
        b[0],
        boolean_node(group, "NOT", equals(a[2], b[2])),
    ):
        pair = boolean_node(group, "AND", pair, condition)

    face_index = nodes.new("GeometryNodeInputIndex")
    corners = nodes.new("GeometryNodeCornersOfFace")
    links.new(face_index.outputs[0], corners.inputs["Face Index"])
    boundary_count, paired = None, None
    for offset in range(3):
        corner = offset_corner(corners.outputs["Corner Index"], offset)
        edge = nodes.new("GeometryNodeEdgesOfCorner")
        links.new(corner, edge.inputs["Corner Index"])
        match = sample(pair, edge.outputs["Next Edge Index"], "EDGE", "BOOLEAN")
        paired = match if paired is None else boolean_node(group, "OR", paired, match)
        rim = boundary(corner)
        if boundary_count is None:
            boundary_count = rim
        else:
            add = nodes.new("FunctionNodeIntegerMath")
            add.operation = "ADD"
            links.new(boundary_count, add.inputs[0])
            links.new(rim, add.inputs[1])
            boundary_count = add.outputs[0]
    selected = boolean_node(
        group, "AND",
        equals(corners.outputs["Total"], 3),
        boolean_node(group, "OR", paired, equals(boundary_count, 3)),
    )
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain, delete.mode = "FACE", "ALL"
    links.new(geometry, delete.inputs["Geometry"])
    links.new(selected, delete.inputs["Selection"])
    return delete.outputs["Geometry"]


def sample_face_camera(group, image):
    """Sample camera XYZ at each planar face's UV center."""
    nodes, links = group.nodes, group.links
    uv = nodes.new("GeometryNodeInputNamedAttribute")
    uv.data_type = "FLOAT_VECTOR"
    uv.inputs["Name"].default_value = "UVMap"
    face_uv = nodes.new("GeometryNodeFieldOnDomain")
    face_uv.data_type = "FLOAT_VECTOR"
    face_uv.domain = "FACE"
    links.new(uv.outputs["Attribute"], face_uv.inputs["Value"])
    texture = nodes.new("GeometryNodeImageTexture")
    texture.interpolation = "Linear"
    texture.extension = "EXTEND"
    links.new(image, texture.inputs["Image"])
    links.new(face_uv.outputs["Value"], texture.inputs["Vector"])
    return texture.outputs["Color"]


def ray_distance(group, camera):
    """Measure the distance from the camera origin to a camera-space point."""
    length = group.nodes.new("ShaderNodeVectorMath")
    length.operation = "LENGTH"
    group.links.new(camera, length.inputs[0])
    return length.outputs["Value"]


def split_depth_surface(group, geometry, face_camera, strength, reference_depth, depth_scale, *,
                        face_distance=None, face_center=None, triangles=False):
    """Split relative ray-distance jumps over the base face-center spacing.

    The jump is scaled by Depth Scale, so a flat projection keeps its faces.
    """
    nodes, links = group.nodes, group.links
    if face_center is None:
        face_center = nodes.new("GeometryNodeInputPosition").outputs[0]
    face_camera = evaluate_field(group, face_camera, "FLOAT_VECTOR", "FACE")
    if face_distance is None:
        face_distance = ray_distance(group, face_camera)
    centers, depths = [], []
    for side in (0, 1):
        corner = nodes.new("GeometryNodeCornersOfEdge")
        corner.inputs["Sort Index"].default_value = side
        face = nodes.new("GeometryNodeFaceOfCorner")
        links.new(corner.outputs["Corner Index"], face.inputs["Corner Index"])
        for data_type, field, results in (
            ("FLOAT_VECTOR", face_center, centers),
            ("FLOAT", face_distance, depths),
        ):
            sample = nodes.new("GeometryNodeFieldAtIndex")
            sample.data_type = data_type
            sample.domain = "FACE"
            links.new(face.outputs["Face Index"], sample.inputs["Index"])
            links.new(field, sample.inputs["Value"])
            results.append(sample.outputs["Value"])
    distance = nodes.new("ShaderNodeVectorMath")
    distance.operation = "DISTANCE"
    for index, center in enumerate(centers):
        links.new(center, distance.inputs[index])
    delta = _math(group, "ABSOLUTE", _math(group, "SUBTRACT", *depths))
    # Depth Scale is the display amplitude of that jump on the projected surface.
    delta = _math(group, "MULTIPLY", delta, depth_scale)
    local_distance = _math(group, "MAXIMUM", _math(group, "MULTIPLY", _math(group, "ADD", *depths), 0.5), 1e-8)
    reference = _math(group, "MAXIMUM", reference_depth, 1e-8)
    # Uniform Scale cancels between the distance jump and local spacing correction.
    # Cross multiplication also avoids dividing by the local distance.
    selected = compare_node(
        group,
        "GREATER_THAN",
        _math(group, "MULTIPLY", _math(group, "MULTIPLY", delta, reference), strength),
        _math(group, "MULTIPLY", _math(group, "MULTIPLY", distance.outputs["Value"], local_distance), 2.5),
    )
    selected = boolean_node(
        group,
        "AND",
        selected,
        compare_node(group, "GREATER_THAN", distance.outputs["Value"], 0.0),
    )
    neighbors = nodes.new("GeometryNodeInputMeshEdgeNeighbors")
    selected = boolean_node(
        group,
        "AND",
        selected,
        compare_node(group, "EQUAL", neighbors.outputs["Face Count"], 2, data_type="INT"),
    )
    cut_edges = nodes.new("GeometryNodeFieldOnDomain")
    cut_edges.data_type = "FLOAT"
    cut_edges.domain = "EDGE"
    links.new(selected, cut_edges.inputs["Value"])
    cut_vertices = nodes.new("GeometryNodeFieldOnDomain")
    cut_vertices.data_type = "FLOAT"
    cut_vertices.domain = "POINT"
    links.new(cut_edges.outputs["Value"], cut_vertices.inputs["Value"])
    corners, cut = store_boolean_attribute(
        group, geometry, CUT_ATTRIBUTE,
        compare_node(group, "GREATER_THAN", cut_vertices.outputs["Value"], 0.0), domain="CORNER",
    )
    split = nodes.new("GeometryNodeSplitEdges")
    links.new(corners, split.inputs["Mesh"])
    links.new(selected, split.inputs["Selection"])
    enabled = boolean_node(
        group,
        "AND",
        compare_node(group, "GREATER_THAN", strength, 0.0),
        compare_node(group, "GREATER_THAN", depth_scale, 0.0),
    )
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(enabled, choose.inputs["Switch"])
    links.new(geometry, choose.inputs["False"])
    links.new(_remove_strip_faces(group, split.outputs["Mesh"], triangles=triangles), choose.inputs["True"])
    return choose.outputs["Output"], face_camera, cut


def limit_depth_surface(
    group, geometry, face_camera, cut_vertex,
    uniform_scale, reference_depth, depth_scale, depth_limit,
):
    """Delete far geometry and preserve the prior boundary for cut detection."""
    nodes, links = group.nodes, group.links
    axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(face_camera, axes.inputs["Vector"])
    face_y = _math(
        group, "MULTIPLY",
        _math(
            group, "SUBTRACT",
            _math(group, "MULTIPLY", axes.outputs["Z"], uniform_scale),
            reference_depth,
        ),
        depth_scale,
    )
    limited = compare_node(group, "GREATER_THAN", face_y, depth_limit)
    statistics = nodes.new("GeometryNodeAttributeStatistic")
    statistics.data_type, statistics.domain = "FLOAT", "FACE"
    links.new(geometry, statistics.inputs["Geometry"])
    links.new(limited, statistics.inputs["Attribute"])
    has_limited = compare_node(group, "GREATER_THAN", statistics.outputs["Max"], 0.0)
    marked, previous_boundary = store_boolean_attribute(
        group, geometry, LIMIT_BOUNDARY_ATTRIBUTE,
        edge_boundary_field(nodes, links),
    )
    delete = nodes.new("GeometryNodeDeleteGeometry")
    delete.domain, delete.mode = "FACE", "ALL"
    links.new(marked, delete.inputs["Geometry"])
    links.new(limited, delete.inputs["Selection"])
    choose = nodes.new("GeometryNodeSwitch")
    choose.input_type = "GEOMETRY"
    links.new(has_limited, choose.inputs["Switch"])
    links.new(geometry, choose.inputs["False"])
    links.new(delete.outputs["Geometry"], choose.inputs["True"])
    return choose.outputs["Output"], cut_vertex, previous_boundary, has_limited


def build_surface_camera(group, original, separated, cut_vertex, strength):
    """Take cut depth from the adjacent face sample along each unchanged ray.

    Depth Split edges and every open boundary left by Depth Mask deletion share
    one replacement, so each cut edge sits on the surface it belongs to.
    """
    nodes, links = group.nodes, group.links
    cut_boundary = evaluate_field(group, edge_boundary_field(nodes, links), "BOOLEAN", "POINT")
    enabled = nodes.new("GeometryNodeSwitch")
    enabled.input_type = "BOOLEAN"
    links.new(compare_node(group, "GREATER_THAN", strength, 0.0), enabled.inputs["Switch"])
    enabled.inputs["False"].default_value = False
    links.new(cut_vertex, enabled.inputs["True"])
    combined = nodes.new("FunctionNodeBooleanMath")
    combined.operation = "OR"
    links.new(enabled.outputs["Output"], combined.inputs[0])
    links.new(cut_boundary, combined.inputs[1])
    enabled = combined.outputs["Boolean"]
    original_axes = group.nodes.new("ShaderNodeSeparateXYZ")
    separated_axes = group.nodes.new("ShaderNodeSeparateXYZ")
    group.links.new(original, original_axes.inputs[0])
    group.links.new(separated, separated_axes.inputs[0])
    ratio = _math(
        group, "DIVIDE", separated_axes.outputs["Z"], original_axes.outputs["Z"]
    )
    projected = group.nodes.new("ShaderNodeVectorMath")
    projected.operation = "SCALE"
    group.links.new(original, projected.inputs[0])
    group.links.new(ratio, projected.inputs[3])
    choose = group.nodes.new("GeometryNodeSwitch")
    choose.input_type = "VECTOR"
    group.links.new(enabled, choose.inputs["Switch"])
    group.links.new(original, choose.inputs["False"])
    group.links.new(projected.outputs[0], choose.inputs["True"])
    return evaluate_field(group, choose.outputs["Output"], "FLOAT_VECTOR", "POINT")


def thicken_depth_surface(group, geometry, thickness, normal_smooth=None):
    """Connect caps with single quads by source vertex and cap identity."""
    nodes, links = group.nodes, group.links
    position = nodes.new("GeometryNodeInputPosition")
    index = nodes.new("GeometryNodeInputIndex")
    # Encode identity in the construction geometry before extrusion. The source
    # surface remains a separate sampling input; no position or ID is stored.
    identity = nodes.new("ShaderNodeCombineXYZ")
    for operation, axis in (("MODULO", "X"), ("DIVIDE", "Z")):
        part = nodes.new("FunctionNodeIntegerMath")
        part.operation = operation
        part.inputs[1].default_value = 4096
        links.new(index.outputs[0], part.inputs[0])
        links.new(part.outputs[0], identity.inputs[axis])
    sheet = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, sheet.inputs["Geometry"])
    links.new(identity.outputs[0], sheet.inputs["Position"])
    saved = sheet.outputs["Geometry"]
    layer_axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs[0], layer_axes.inputs[0])
    row = nodes.new("FunctionNodeIntegerMath")
    row.operation = "MULTIPLY"
    row.inputs[1].default_value = 4096
    links.new(layer_axes.outputs["Z"], row.inputs[0])
    vertex = nodes.new("FunctionNodeIntegerMath")
    vertex.operation = "ADD"
    links.new(layer_axes.outputs["X"], vertex.inputs[0])
    links.new(row.outputs[0], vertex.inputs[1])
    source_index = vertex.outputs[0]
    source_position = sample_field(group, geometry, position.outputs[0], "FLOAT_VECTOR", index=source_index)
    source_thickness = sample_field(group, geometry, thickness, "FLOAT", index=source_index)

    extrude = nodes.new("GeometryNodeExtrudeMesh")
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    extrusion_offset = nodes.new("ShaderNodeCombineXYZ")
    extrusion_offset.inputs["Y"].default_value = -1.0
    links.new(extrusion_offset.outputs[0], extrude.inputs["Offset"])
    links.new(saved, extrude.inputs["Mesh"])
    sides = nodes.new("GeometryNodeSeparateGeometry")
    sides.domain = "FACE"
    links.new(extrude.outputs["Mesh"], sides.inputs["Geometry"])
    links.new(extrude.outputs["Side"], sides.inputs["Selection"])
    offset = nodes.new("ShaderNodeCombineXYZ")
    offset.inputs["Y"].default_value = -1.0
    back = nodes.new("GeometryNodeSetPosition")
    links.new(saved, back.inputs["Geometry"])
    links.new(offset.outputs[0], back.inputs["Offset"])
    flip_back = nodes.new("GeometryNodeFlipFaces")
    links.new(back.outputs["Geometry"], flip_back.inputs["Mesh"])
    flip_sides = nodes.new("GeometryNodeFlipFaces")
    links.new(sides.outputs["Selection"], flip_sides.inputs["Mesh"])
    join = nodes.new("GeometryNodeJoinGeometry")
    rear = flip_back.outputs["Mesh"]
    rim = flip_sides.outputs["Mesh"]
    back_parts = nodes.new("GeometryNodeJoinGeometry")
    links.new(rear, back_parts.inputs["Geometry"])
    links.new(rim, back_parts.inputs["Geometry"])
    rear = back_parts.outputs["Geometry"]
    for value in (
        saved,
        rear,
    ):
        links.new(value, join.inputs["Geometry"])
    construction = join.outputs["Geometry"]
    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.mode = "ALL"
    merge.inputs["Distance"].default_value = 0.1
    links.new(construction, merge.inputs["Geometry"])
    displacement = nodes.new("ShaderNodeCombineXYZ")
    distance = _math(group, "MULTIPLY", layer_axes.outputs["Y"], source_thickness)
    links.new(distance, displacement.inputs["Y"])
    restored = nodes.new("ShaderNodeVectorMath")
    restored.operation = "ADD"
    links.new(source_position, restored.inputs[0])
    links.new(displacement.outputs[0], restored.inputs[1])
    result = nodes.new("GeometryNodeSetPosition")
    links.new(merge.outputs["Geometry"], result.inputs["Geometry"])
    links.new(restored.outputs[0], result.inputs["Position"])
    if normal_smooth is not None:
        normal = nodes.new("GeometryNodeInputNormal")
        blur = nodes.new("GeometryNodeBlurAttribute")
        blur.data_type = "FLOAT_VECTOR"
        blur.inputs["Iterations"].default_value = normal_smooth
        links.new(normal.outputs[0], blur.inputs["Value"])
        normalize = nodes.new("ShaderNodeVectorMath")
        normalize.operation = "NORMALIZE"
        links.new(blur.outputs[0], normalize.inputs[0])
        source_normal = sample_field(group, geometry, normalize.outputs[0], "FLOAT_VECTOR", index=source_index)
        normal_offset = nodes.new("ShaderNodeVectorMath")
        normal_offset.operation = "SCALE"
        links.new(source_normal, normal_offset.inputs[0])
        links.new(distance, normal_offset.inputs[3])
        links.new(normal_offset.outputs[0], restored.inputs[1])
        nodes.remove(displacement)
    return {
        "geometry": result.outputs["Geometry"],
        "front": source_position,
        "source_index": source_index,
        "position": restored.outputs[0],
        "position_input": result.inputs["Position"],
    }


def _projection_math(nodes, operation):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    return node


def project_depth_surface(
    group, geometry, camera_position, uniform_scale, reference_depth, depth_scale
):
    """Interpolate the rectangular plane into the model camera coordinates."""
    nodes, links = group.nodes, group.links
    scaled = nodes.new("ShaderNodeVectorMath")
    scaled.operation = "SCALE"
    links.new(camera_position, scaled.inputs[0])
    links.new(uniform_scale, scaled.inputs[3])
    separate = nodes.new("ShaderNodeSeparateXYZ")
    links.new(scaled.outputs["Vector"], separate.inputs["Vector"])
    relative_depth = _projection_math(nodes, "SUBTRACT")
    links.new(separate.outputs["Z"], relative_depth.inputs[0])
    links.new(reference_depth, relative_depth.inputs[1])
    front = _projection_math(nodes, "MULTIPLY")
    links.new(relative_depth.outputs[0], front.inputs[0])
    links.new(depth_scale, front.inputs[1])

    negative_z = _projection_math(nodes, "MULTIPLY")
    negative_z.inputs[1].default_value = -1.0
    links.new(separate.outputs["Y"], negative_z.inputs[0])
    projected = nodes.new("ShaderNodeCombineXYZ")
    links.new(separate.outputs["X"], projected.inputs["X"])
    links.new(front.outputs[0], projected.inputs["Y"])
    links.new(negative_z.outputs[0], projected.inputs["Z"])
    current_position = nodes.new("GeometryNodeInputPosition")
    blend = nodes.new("ShaderNodeMix")
    blend.data_type = "VECTOR"
    blend.clamp_factor = False
    links.new(depth_scale, blend.inputs[0])
    links.new(current_position.outputs["Position"], blend.inputs[4])
    links.new(projected.outputs["Vector"], blend.inputs[5])
    blended_axes = nodes.new("ShaderNodeSeparateXYZ")
    links.new(blend.outputs["Result"], blended_axes.inputs["Vector"])
    surface_position = nodes.new("ShaderNodeCombineXYZ")
    links.new(blended_axes.outputs["X"], surface_position.inputs["X"])
    links.new(front.outputs[0], surface_position.inputs["Y"])
    links.new(blended_axes.outputs["Z"], surface_position.inputs["Z"])
    project_geometry = nodes.new("GeometryNodeSetPosition")
    links.new(geometry, project_geometry.inputs["Geometry"])
    links.new(surface_position.outputs["Vector"], project_geometry.inputs["Position"])

    return remove_attribute_pattern(group, project_geometry.outputs["Geometry"], "_o_*")
