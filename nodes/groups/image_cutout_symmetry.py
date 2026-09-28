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


def _face_edge_fields(group):
    """Map face corners to edges while keeping the first four corners."""
    nodes, links = group.nodes, group.links
    index = nodes.new('GeometryNodeInputIndex')
    corner = nodes.new('GeometryNodeFaceOfCorner')
    links.new(index.outputs[0], corner.inputs['Corner Index'])
    first_four = compare_node(group, 'LESS_THAN', corner.outputs['Index in Face'], 4, data_type='INT')
    edges = nodes.new('GeometryNodeEdgesOfCorner')
    links.new(index.outputs[0], edges.inputs['Corner Index'])
    face = nodes.new('GeometryNodeInputMeshFaceNeighbors')
    return edges.outputs['Next Edge Index'], first_four, face.outputs['Vertex Count']


def _face_edge_count(group, value, face_edges):
    """Count matching edges among a face's first four corners."""
    edge_index, first_four, vertex_count = face_edges
    sample = group.nodes.new('GeometryNodeFieldAtIndex')
    sample.data_type, sample.domain = 'BOOLEAN', 'EDGE'
    group.links.new(value, sample.inputs['Value'])
    group.links.new(edge_index, sample.inputs['Index'])
    selected = boolean_node(group, 'AND', sample.outputs['Value'], first_four)
    corners = evaluate_field(group, selected, 'FLOAT', 'CORNER')
    mean = evaluate_field(group, corners, 'FLOAT', 'FACE')
    return _math(group, 'MULTIPLY', mean, vertex_count)


def _delete_bridge_faces(group, geometry, boundary, face_edges):
    """Delete the faces left bridging two openings of a cut."""
    count = _face_edge_count(group, boundary, face_edges)
    return _delete_faces(group, geometry, compare_node(group, 'GREATER_THAN', count, 1.5))


def _delete_flat_faces(group, geometry, height, distance):
    """Delete the faces lying on the symmetry plane; they mirror onto themselves."""
    nodes, links = group.nodes, group.links
    normal = nodes.new('GeometryNodeInputNormal')
    normal_axes = nodes.new('ShaderNodeSeparateXYZ')
    links.new(normal.outputs[0], normal_axes.inputs[0])
    center = evaluate_field(group, height, 'FLOAT', 'FACE')
    return _delete_faces(
        group, geometry,
        boolean_node(
            group, 'AND',
            compare_node(group, 'LESS_THAN', center, distance),
            compare_node(group, 'GREATER_THAN', _math(group, 'ABSOLUTE', normal_axes.outputs['Y']), 1 - 1e-3),
        ),
    )


def _delete_crease_faces(group, geometry, edge_height, face_count, face_edges, distance):
    """Delete the faces the fold leaves sharing an interior edge on the plane."""
    plane = compare_node(group, 'LESS_THAN', edge_height, distance)
    crease = boolean_node(
        group, 'AND', plane,
        compare_node(group, 'EQUAL', face_count, 2, data_type='INT'),
    )
    count = _face_edge_count(group, crease, face_edges)
    return _delete_faces(group, geometry, compare_node(group, 'GREATER_THAN', count, 0.0))


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


def _seam_field(group, on_plane):
    """Report the cut ring the folded front leaves on the symmetry plane."""
    boundary = evaluate_field(group, edge_boundary_field(group.nodes, group.links), 'BOOLEAN', 'POINT')
    return boolean_node(group, 'AND', boundary, on_plane)


def _falloff(group, center, rings):
    """Blur a 0/1 center into a falloff over the requested rings."""
    blur = group.nodes.new('GeometryNodeBlurAttribute')
    blur.data_type = 'FLOAT'
    blur.inputs['Iterations'].default_value = rings
    group.links.new(center, blur.inputs['Value'])
    return _math(group, 'MAXIMUM', center, blur.outputs[0])


def _snap_to_plane(group, geometry, selection, target):
    """Move the selected points onto the symmetry plane."""
    nodes, links = group.nodes, group.links
    place = nodes.new('GeometryNodeSetPosition')
    links.new(geometry, place.inputs['Geometry'])
    links.new(selection, place.inputs['Selection'])
    links.new(target, place.inputs['Position'])
    return place.outputs[0]


def _relax_seam(group, geometry, seam, retract, smooth, plane_position):
    """Relax the cut seam in three dimensions and keep the cut on the plane."""
    relaxed = pinned_smooth(
        group, geometry, smooth, _falloff(group, seam, SMOOTH_RINGS),
        pin_boundary=True,
    )
    return _snap_to_plane(group, relaxed, boolean_node(group, 'OR', seam, retract), plane_position)


def _relax_fill(group, geometry, fill, smooth):
    """Relax the fill faces on the welded mesh and fade outward from them."""
    return pinned_smooth(
        group, geometry, smooth, _falloff(group, fill, SMOOTH_RINGS),
        weight=0.2, pin_boundary=False, cache_region=True,
    )


def _build_wall(group, front, boundary, plane_position):
    """Close the selected boundary edges onto the symmetry plane and mark the fill."""
    nodes, links = group.nodes, group.links
    extrude = nodes.new('GeometryNodeExtrudeMesh')
    extrude.mode = 'EDGES'
    extrude.inputs['Offset Scale'].default_value = 0
    links.new(front, extrude.inputs['Mesh'])
    links.new(boundary, extrude.inputs['Selection'])
    geometry = _snap_to_plane(group, extrude.outputs['Mesh'], extrude.outputs['Top'], plane_position)
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
    merge_distance = 1e-6
    position = nodes.new('GeometryNodeInputPosition')
    components = nodes.new('ShaderNodeSeparateXYZ')
    links.new(position.outputs[0], components.inputs[0])
    height = _math(group, 'ABSOLUTE', components.outputs['Y'])
    beyond = compare_node(group, 'GREATER_THAN', components.outputs['Y'], merge_distance)
    on_plane = compare_node(group, 'LESS_THAN', height, merge_distance)
    plane_position = nodes.new('ShaderNodeCombineXYZ')
    links.new(components.outputs['X'], plane_position.inputs['X'])
    links.new(components.outputs['Z'], plane_position.inputs['Z'])
    plane_position = plane_position.outputs[0]
    neighbors = nodes.new('GeometryNodeInputMeshEdgeNeighbors')
    face_count = neighbors.outputs['Face Count']
    face_edges = _face_edge_fields(group)
    edge_height = _math(group, 'MAXIMUM', *_edge_abs_y(group))
    retract = boolean_node(group, 'OR', on_plane, beyond)
    is_boundary = compare_node(group, 'EQUAL', face_count, 1, data_type='INT')
    front = _delete_beyond_plane(group, aligned, beyond)
    front = _delete_bridge_faces(group, front, is_boundary, face_edges)
    # 贴合带内和跨界保留的面都折回对称面，切口环因此落在平面上。
    front = _snap_to_plane(group, front, retract, plane_position)
    seam_field = _seam_field(group, on_plane)
    shade = nodes.new('GeometryNodeSetShadeSmooth')
    shade.domain = 'FACE'
    links.new(front, shade.inputs['Geometry'])
    front = store_float_attribute(group, shade.outputs[0], FACE_ATTRIBUTE, 1., domain='FACE')
    front = _relax_seam(
        group, front, seam_field, retract, inputs['Smooth'], plane_position,
    )
    # 松弛会把点压回平面，贴平的面和内部贴平边要在松弛之后再清一次。
    front = _delete_flat_faces(group, front, height, merge_distance)
    front = _delete_crease_faces(group, front, edge_height, face_count, face_edges, merge_distance)
    # 切口环本身贴在对称面上并靠镜像焊住，只有不落在这条环上的边界边才需要补面。
    wall = nodes.new('FunctionNodeBooleanMath')
    wall.operation = 'AND'
    links.new(is_boundary, wall.inputs[0])
    links.new(compare_node(group, 'GREATER_THAN', edge_height, merge_distance), wall.inputs[1])
    walled, fill = _build_wall(group, front, wall.outputs[0], plane_position)
    body = nodes.new('GeometryNodeSwitch')
    body.input_type = 'GEOMETRY'
    links.new(inputs['Fill Sides'], body.inputs['Switch'])
    links.new(front, body.inputs['False'])
    links.new(walled, body.inputs['True'])
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
    relaxed_fill = _relax_fill(
        group, merged, fill, inputs['Smooth'],
    )
    fill_enabled = nodes.new('GeometryNodeSwitch')
    fill_enabled.input_type = 'GEOMETRY'
    links.new(inputs['Fill Sides'], fill_enabled.inputs['Switch'])
    links.new(merged, fill_enabled.inputs['False'])
    links.new(relaxed_fill, fill_enabled.inputs['True'])
    geometry = fill_enabled.outputs['Output']
    geometry = store_float_attribute(group, geometry, AXIS_ATTRIBUTE, 1., domain='FACE')
    orient = nodes.new('GeometryNodeTransform')
    orient.inputs['Rotation'].default_value = Matrix.Rotation(1.5707963267948966, 4, 'Z').to_euler()
    links.new(geometry, orient.inputs['Geometry'])
    # Fade the material normal map near the symmetry plane so the weld shades smoother.
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
