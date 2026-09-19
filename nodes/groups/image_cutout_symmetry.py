"""Mirror completed depth geometry and fill matching boundaries."""
import bpy
from mathutils import Matrix

from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME

from ..common.nodes import (
    interface_socket, group_input, float_input, bool_input, vector_input,
    compare_node, boolean_node, evaluate_field,
    store_boolean_attribute, store_float_attribute, read_float_attribute,
    remove_attribute_pattern, prepare_node_group,
)
from ..common.depth_surface import _math
from ..common.normal_map import ROTATION_ATTRIBUTE, FACE_ATTRIBUTE, AXIS_ATTRIBUTE
from ..common.direction import symmetry_legacy_direction_to_canonical
from ..common.smoothing import edge_boundary_field, pinned_smooth

NODE_GROUP_NAME = "O Image Cutout Symmetry"

# 切口环与补面衔接带各自向外覆盖的圈数。
SMOOTH_RINGS = 4

# 补面标记：挤出之后按面记下补面，作为补面平滑的范围。
WELD_ATTRIBUTE = '_o_symmetry_weld'


# 对称面附近按中位边长的倍数降低法线贴图强度。
SEAM_NORMAL_BAND = 4


def _align_front(group, geometry, controls):
    """Align existing geometry with the fixed XY symmetry plane."""
    nodes, links = group.nodes, group.links
    direction = symmetry_legacy_direction_to_canonical(group, controls['Direction'])
    align = nodes.new('FunctionNodeAlignEulerToVector')
    align.axis = 'Y'
    links.new(direction, align.inputs['Vector'])
    position = nodes.new('GeometryNodeInputPosition')
    rotate = nodes.new('ShaderNodeVectorRotate')
    rotate.rotation_type = 'EULER_XYZ'
    rotate.invert = True
    links.new(position.outputs[0], rotate.inputs['Vector'])
    links.new(align.outputs['Rotation'], rotate.inputs['Rotation'])
    offset = nodes.new('ShaderNodeCombineXYZ')
    offset_value = nodes.new('ShaderNodeMath')
    offset_value.operation = 'MULTIPLY'
    offset_value.inputs[1].default_value = -1.0
    links.new(controls['Offset'], offset_value.inputs[0])
    links.new(offset_value.outputs[0], offset.inputs['Y'])
    offset_position = nodes.new('ShaderNodeVectorMath')
    offset_position.operation = 'ADD'
    links.new(rotate.outputs[0], offset_position.inputs[0])
    links.new(offset.outputs[0], offset_position.inputs[1])
    scale_vector = nodes.new('ShaderNodeCombineXYZ')
    scale_vector.inputs['X'].default_value = 1
    scale_vector.inputs['Z'].default_value = 1
    links.new(controls['Scale'], scale_vector.inputs['Y'])
    scale = nodes.new('ShaderNodeVectorMath')
    scale.operation = 'MULTIPLY'
    links.new(offset_position.outputs[0], scale.inputs[0])
    links.new(scale_vector.outputs[0], scale.inputs[1])
    place = nodes.new('GeometryNodeSetPosition')
    links.new(geometry, place.inputs['Geometry'])
    links.new(scale.outputs[0], place.inputs['Position'])
    store = nodes.new('GeometryNodeStoreNamedAttribute')
    store.data_type, store.domain = 'FLOAT_VECTOR', 'FACE'
    store.inputs['Name'].default_value = ROTATION_ATTRIBUTE
    links.new(place.outputs[0], store.inputs['Geometry'])
    links.new(align.outputs['Rotation'], store.inputs['Value'])
    return store.outputs['Geometry']


def _boundary_edge_field(group):
    """Report one on edges that carry a single face."""
    neighbors = group.nodes.new('GeometryNodeInputMeshEdgeNeighbors')
    return compare_node(group, 'EQUAL', neighbors.outputs['Face Count'], 1, data_type='INT')


def _beyond_plane_field(group, distance):
    """Report the points sitting farther than the weld distance past the plane."""
    nodes = group.nodes
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    group.links.new(position.outputs[0], components.inputs[0])
    return compare_node(group, 'GREATER_THAN', components.outputs['Y'], distance)


def _on_plane_field(group, distance):
    """Report the points sitting within the weld distance of the plane."""
    nodes = group.nodes
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    group.links.new(position.outputs[0], components.inputs[0])
    return compare_node(group, 'LESS_THAN', _math(group, 'ABSOLUTE', components.outputs['Y']), distance)


def _merge_points(group, geometry, selection, distance):
    """Weld the selected points that share a position."""
    nodes, links = group.nodes, group.links
    merge = nodes.new('GeometryNodeMergeByDistance')
    links.new(geometry, merge.inputs['Geometry'])
    links.new(selection, merge.inputs['Selection'])
    if isinstance(distance, (int, float)):
        merge.inputs['Distance'].default_value = distance
    else:
        links.new(distance, merge.inputs['Distance'])
    return merge.outputs[0]


def _delete_faces(group, geometry, selection):
    """Delete the selected faces and the geometry only they used."""
    nodes, links = group.nodes, group.links
    delete = nodes.new('GeometryNodeDeleteGeometry')
    delete.domain, delete.mode = 'FACE', 'ALL'
    links.new(geometry, delete.inputs['Geometry'])
    links.new(selection, delete.inputs['Selection'])
    return delete.outputs[0]


def _delete_beyond_plane(group, geometry, beyond):
    """Delete the faces whose points all sit beyond the symmetry plane."""
    # 点域求值让面域选择按「全部点越界」删除，跨界的面连几何一起留给切口回拉。
    return _delete_faces(group, geometry, evaluate_field(group, beyond, 'BOOLEAN', 'POINT'))


def _corner_edge(group, corner, offset, value):
    """Read an edge value at one corner around a face."""
    nodes, links = group.nodes, group.links
    shifted = nodes.new('GeometryNodeOffsetCornerInFace')
    links.new(corner, shifted.inputs['Corner Index'])
    shifted.inputs['Offset'].default_value = offset
    edges = nodes.new('GeometryNodeEdgesOfCorner')
    links.new(shifted.outputs['Corner Index'], edges.inputs['Corner Index'])
    sample = nodes.new('GeometryNodeFieldAtIndex')
    sample.data_type, sample.domain = 'BOOLEAN', 'EDGE'
    links.new(value, sample.inputs['Value'])
    links.new(edges.outputs['Next Edge Index'], sample.inputs['Index'])
    return sample.outputs['Value']


def _boundary_edge_count(group):
    """Count the edges carrying a single face around each face."""
    nodes, links = group.nodes, group.links
    boundary = _boundary_edge_field(group)
    index = nodes.new('GeometryNodeInputIndex')
    corners = nodes.new('GeometryNodeCornersOfFace')
    links.new(index.outputs[0], corners.inputs['Face Index'])
    # 第四个偏移在三角形上绕回第一条边，按角数把它归零。
    quad = compare_node(group, 'GREATER_THAN', corners.outputs['Total'], 3, data_type='INT')
    count = None
    for offset in range(4):
        term = _corner_edge(group, corners.outputs['Corner Index'], offset, boundary)
        if offset == 3:
            masked = nodes.new('GeometryNodeSwitch')
            masked.input_type = 'FLOAT'
            masked.inputs['False'].default_value = 0.0
            links.new(quad, masked.inputs['Switch'])
            links.new(term, masked.inputs['True'])
            term = masked.outputs['Output']
        count = term if count is None else _math(group, 'ADD', count, term)
    return count


def _delete_bridge_faces(group, geometry):
    """Delete the faces left bridging two openings of a cut."""
    return _delete_faces(group, geometry, compare_node(group, 'GREATER_THAN', _boundary_edge_count(group), 1.5))


def _delete_flat_faces(group, geometry, distance):
    """Delete the faces lying on the symmetry plane; they mirror onto themselves."""
    nodes, links = group.nodes, group.links
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs[0], components.inputs[0])
    normal = nodes.new('GeometryNodeInputNormal')
    normal_axes = nodes.new('ShaderNodeSeparateXYZ')
    links.new(normal.outputs[0], normal_axes.inputs[0])
    center = evaluate_field(group, _math(group, 'ABSOLUTE', components.outputs['Y']), 'FLOAT', 'FACE')
    return _delete_faces(
        group, geometry,
        boolean_node(
            group, 'AND',
            compare_node(group, 'LESS_THAN', center, distance),
            compare_node(group, 'GREATER_THAN', _math(group, 'ABSOLUTE', normal_axes.outputs['Y']), 1 - 1e-3),
        ),
    )


def _delete_crease_faces(group, geometry, distance):
    """Delete the faces the fold leaves sharing an interior edge on the plane."""
    nodes, links = group.nodes, group.links
    heights = _edge_abs_y(group)
    plane = nodes.new('FunctionNodeBooleanMath')
    plane.operation = 'AND'
    links.new(compare_node(group, 'LESS_THAN', heights[0], distance), plane.inputs[0])
    links.new(compare_node(group, 'LESS_THAN', heights[1], distance), plane.inputs[1])
    neighbors = nodes.new('GeometryNodeInputMeshEdgeNeighbors')
    crease = nodes.new('FunctionNodeBooleanMath')
    crease.operation = 'AND'
    links.new(plane.outputs[0], crease.inputs[0])
    links.new(compare_node(group, 'EQUAL', neighbors.outputs['Face Count'], 2, data_type='INT'), crease.inputs[1])
    index = nodes.new('GeometryNodeInputIndex')
    corners = nodes.new('GeometryNodeCornersOfFace')
    links.new(index.outputs[0], corners.inputs['Face Index'])
    selected = None
    for offset in range(4):
        term = _corner_edge(group, corners.outputs['Corner Index'], offset, crease.outputs[0])
        selected = term if selected is None else boolean_node(group, 'OR', selected, term)
    return _delete_faces(group, geometry, selected)


def _off_plane_edge_field(group, distance):
    """Report one on edges that keep an endpoint farther than the weld distance."""
    heights = _edge_abs_y(group)
    return compare_node(group, 'GREATER_THAN', _math(group, 'MAXIMUM', heights[0], heights[1]), distance)


def _edge_abs_y(group):
    """Return both endpoint heights on the symmetry axis for an edge."""
    edge = group.nodes.new('GeometryNodeInputMeshEdgeVertices')
    heights = []
    for socket in ('Position 1', 'Position 2'):
        axis = group.nodes.new('ShaderNodeSeparateXYZ')
        group.links.new(edge.outputs[socket], axis.inputs[0])
        heights.append(_math(group, 'ABSOLUTE', axis.outputs['Y']))
    return heights


def _mirror(group, geometry):
    mirror = group.nodes.new('GeometryNodeTransform')
    mirror.inputs['Scale'].default_value = (1, -1, 1)
    group.links.new(geometry, mirror.inputs['Geometry'])
    flip = group.nodes.new('GeometryNodeFlipFaces')
    group.links.new(mirror.outputs[0], flip.inputs['Mesh'])
    return flip.outputs[0]


def _seam_field(group, distance):
    """Report the cut ring the folded front leaves on the symmetry plane."""
    boundary = evaluate_field(group, edge_boundary_field(group.nodes, group.links), 'BOOLEAN', 'POINT')
    return boolean_node(group, 'AND', boundary, _on_plane_field(group, distance))


def _falloff(group, center, rings):
    """Blur a 0/1 center into a falloff over the requested rings."""
    blur = group.nodes.new('GeometryNodeBlurAttribute')
    blur.data_type = 'FLOAT'
    blur.inputs['Iterations'].default_value = rings
    group.links.new(center, blur.inputs['Value'])
    return _math(group, 'MAXIMUM', center, blur.outputs[0])


def _snap_to_plane(group, geometry, selection):
    """Move the selected points onto the symmetry plane."""
    nodes, links = group.nodes, group.links
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs[0], components.inputs[0])
    target = nodes.new('ShaderNodeCombineXYZ')
    links.new(components.outputs['X'], target.inputs['X'])
    links.new(components.outputs['Z'], target.inputs['Z'])
    place = nodes.new('GeometryNodeSetPosition')
    links.new(geometry, place.inputs['Geometry'])
    links.new(selection, place.inputs['Selection'])
    links.new(target.outputs[0], place.inputs['Position'])
    return place.outputs[0]


def _relax_seam(group, geometry, seam, retract, smooth):
    """Relax the cut seam in three dimensions and keep the cut on the plane."""
    relaxed = pinned_smooth(
        group, geometry, smooth, _falloff(group, seam, SMOOTH_RINGS),
        pin_boundary=True,
    )
    return _snap_to_plane(group, relaxed, boolean_node(group, 'OR', seam, retract))


def _relax_fill(group, geometry, fill, smooth):
    """Relax the fill faces on the welded mesh and fade outward from them."""
    return pinned_smooth(
        group, geometry, smooth, _falloff(group, fill, SMOOTH_RINGS),
        weight=0.2, pin_boundary=False,
    )


def _build_wall(group, front, boundary):
    """Close the selected boundary edges onto the symmetry plane and mark the fill."""
    nodes, links = group.nodes, group.links
    extrude = nodes.new('GeometryNodeExtrudeMesh')
    extrude.mode = 'EDGES'
    extrude.inputs['Offset Scale'].default_value = 0
    links.new(front, extrude.inputs['Mesh'])
    links.new(boundary, extrude.inputs['Selection'])
    geometry = _snap_to_plane(group, extrude.outputs['Mesh'], extrude.outputs['Top'])
    # 挤出之后再标记补面：范围就是补面本身连同它的边界线，挤出不会改变它。
    fill = evaluate_field(group, extrude.outputs['Side'], 'BOOLEAN', 'POINT')
    geometry, fill = store_boolean_attribute(group, geometry, WELD_ATTRIBUTE, fill, domain='FACE')
    store = nodes.new('GeometryNodeStoreNamedAttribute')
    store.data_type, store.domain = 'FLOAT', 'FACE'
    store.inputs['Name'].default_value = FACE_ATTRIBUTE
    store.inputs['Value'].default_value = 3
    links.new(geometry, store.inputs['Geometry'])
    links.new(extrude.outputs['Side'], store.inputs['Selection'])
    return store.outputs[0], fill


def build_image_cutout_symmetry_group():
    existing = bpy.data.node_groups.get(NODE_GROUP_NAME)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(NODE_GROUP_NAME, 'GeometryNodeTree')
    group.is_modifier, group.use_fake_user = True, True
    group.color_tag = 'GEOMETRY'
    interface_socket(group, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    vector_input(group, 'Direction', (0, 0, 1), subtype='DIRECTION').description = 'Align this direction with the local symmetry axis.'
    float_input(group, 'Offset', 0, minimum=-10, maximum=10, subtype='DISTANCE').description = 'Offset geometry along the aligned symmetry axis before scaling.'
    float_input(group, 'Scale', 1, maximum=2).description = 'Scale the offset geometry along the aligned symmetry axis.'
    options = group.interface.new_panel(name='Options', default_closed=True)
    bool_input(group, 'Fill Sides', True, parent=options).description = 'Connect matching front and mirrored boundaries.'
    smooth = interface_socket(group, 'Smooth', 'INPUT', 'NodeSocketInt', options)
    smooth.default_value, smooth.min_value, smooth.max_value = 4, 0, 16
    smooth.description = 'Smooth the cut ring and the fill band around the outline and the fill, each over four rings. Zero keeps both raw.'
    merge = float_input(group, 'Merge Distance', 0.001, minimum=0, subtype='DISTANCE', parent=options)
    merge.description = 'Weld mirrored geometry within this distance of the symmetry plane; boundaries farther away get filled.'
    interface_socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    nodes, links = group.nodes, group.links
    inputs = group_input(nodes, set()).outputs
    aligned = _align_front(group, inputs['Geometry'], inputs)
    edge = nodes.new('GeometryNodeInputMeshEdgeVertices')
    edge_length = nodes.new('ShaderNodeVectorMath')
    edge_length.operation = 'DISTANCE'
    links.new(edge.outputs['Position 1'], edge_length.inputs[0])
    links.new(edge.outputs['Position 2'], edge_length.inputs[1])
    statistics = nodes.new('GeometryNodeAttributeStatistic')
    statistics.data_type, statistics.domain = 'FLOAT', 'EDGE'
    links.new(aligned, statistics.inputs['Geometry'])
    links.new(edge_length.outputs['Value'], statistics.inputs['Attribute'])
    # 合并距离同时决定平面的贴合带和补面边界，两者一致才不会留下细小补面。
    merge_distance = _math(group, 'MAXIMUM', inputs['Merge Distance'], 1e-6)
    beyond = _beyond_plane_field(group, merge_distance)
    on_plane = _on_plane_field(group, merge_distance)
    retract = boolean_node(group, 'OR', on_plane, beyond)
    is_boundary = _boundary_edge_field(group)
    front = _delete_beyond_plane(group, aligned, beyond)
    front = _delete_bridge_faces(group, front)
    # 贴合带内和跨界保留的面都折回对称面，切口环因此落在平面上。
    front = _snap_to_plane(group, front, retract)
    seam_field = _seam_field(group, merge_distance)
    shade = nodes.new('GeometryNodeSetShadeSmooth')
    shade.domain = 'FACE'
    links.new(front, shade.inputs['Geometry'])
    front = store_float_attribute(group, shade.outputs[0], FACE_ATTRIBUTE, 1., domain='FACE')
    front = _relax_seam(group, front, seam_field, retract, inputs['Smooth'])
    # 松弛会把点压回平面，贴平的面和内部贴平边要在松弛之后再清一次。
    front = _delete_flat_faces(group, front, merge_distance)
    front = _delete_crease_faces(group, front, merge_distance)
    fill_iterations = nodes.new('GeometryNodeSwitch')
    fill_iterations.input_type = 'INT'
    fill_iterations.inputs['False'].default_value = 0
    links.new(inputs['Fill Sides'], fill_iterations.inputs['Switch'])
    links.new(inputs['Smooth'], fill_iterations.inputs['True'])
    # 切口环本身贴在对称面上并靠镜像焊住，只有不落在这条环上的边界边才需要补面。
    wall = nodes.new('FunctionNodeBooleanMath')
    wall.operation = 'AND'
    links.new(is_boundary, wall.inputs[0])
    links.new(_off_plane_edge_field(group, merge_distance), wall.inputs[1])
    walled, fill = _build_wall(group, front, wall.outputs[0])
    wall_shade = nodes.new('GeometryNodeSetShadeSmooth')
    wall_shade.domain = 'FACE'
    links.new(compare_node(group, 'EQUAL', read_float_attribute(group, FACE_ATTRIBUTE), 3), wall_shade.inputs['Selection'])
    links.new(walled, wall_shade.inputs['Geometry'])
    body = nodes.new('GeometryNodeSwitch')
    body.input_type = 'GEOMETRY'
    links.new(inputs['Fill Sides'], body.inputs['Switch'])
    links.new(front, body.inputs['False'])
    links.new(wall_shade.outputs[0], body.inputs['True'])
    mark_back = nodes.new('GeometryNodeStoreNamedAttribute')
    mark_back.data_type, mark_back.domain = 'FLOAT', 'FACE'
    mark_back.inputs['Name'].default_value = FACE_ATTRIBUTE
    mark_back.inputs['Value'].default_value = 2
    links.new(_mirror(group, body.outputs[0]), mark_back.inputs['Geometry'])
    links.new(compare_node(group, 'EQUAL', read_float_attribute(group, FACE_ATTRIBUTE), 1), mark_back.inputs['Selection'])
    join = nodes.new('GeometryNodeJoinGeometry')
    for geometry in (body.outputs[0], mark_back.outputs['Geometry']):
        links.new(geometry, join.inputs[0])
    # 平面附近的点已经折到平面上，接缝两侧位置重合；合并只作用在这条带内。
    merged = _merge_points(group, join.outputs[0], on_plane, merge_distance)
    # 先让镜像焊住接缝，再松弛补面和它外侧的衔接带。
    geometry = _relax_fill(group, merged, fill, fill_iterations.outputs[0])
    geometry = store_float_attribute(group, geometry, AXIS_ATTRIBUTE, 1., domain='FACE')
    orient = nodes.new('GeometryNodeTransform')
    orient.inputs['Rotation'].default_value = Matrix.Rotation(1.5707963267948966, 4, 'Z').to_euler()
    links.new(geometry, orient.inputs['Geometry'])
    # Fade the material normal map near the symmetry plane so the weld shades smoother.
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs[0], components.inputs[0])
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.interpolation_type = 'SMOOTHSTEP'
    ramp.clamp = True
    links.new(_math(group, 'ABSOLUTE', components.outputs['X']), ramp.inputs['Value'])
    ramp.inputs['From Min'].default_value = 0.0
    links.new(_math(group, 'MULTIPLY', statistics.outputs['Median'], SEAM_NORMAL_BAND), ramp.inputs['From Max'])
    ramp.inputs['To Min'].default_value = 1.0
    ramp.inputs['To Max'].default_value = 0.0
    reduction = _math(
        group, 'MAXIMUM',
        read_float_attribute(group, NORMAL_REDUCTION_ATTRIBUTE_NAME), ramp.outputs['Result'],
    )
    geometry = store_float_attribute(
        group, orient.outputs[0], NORMAL_REDUCTION_ATTRIBUTE_NAME, reduction,
    )
    geometry = remove_attribute_pattern(group, geometry, '_o_*')
    links.new(geometry, nodes.new('NodeGroupOutput').inputs['Geometry'])
    prepare_node_group(group)
    return group
