"""Build O Image Layer."""
import bpy
from anyimage.common.material import IMAGE_MATERIAL_NODE_GROUP_NAME
from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from ..common.shader import build_material_nodes, connect_material_outputs
from ..common.normal_map import transform_object_normal_color


def build_image_layer_group():
    group_name = IMAGE_MATERIAL_NODE_GROUP_NAME
    existing = bpy.data.node_groups.get(group_name)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    interface = group.interface
    input_sockets = [('Color', 'NodeSocketColor'), ('Alpha', 'NodeSocketFloat'), ('Bump Scale', 'NodeSocketFloat')]
    input_sockets.insert(2, ('Normal', 'NodeSocketColor'))
    input_sockets.insert(3, ('Normal Scale', 'NodeSocketFloat'))
    input_sockets.insert(4, ('Object Space', 'NodeSocketBool'))
    input_sockets.insert(2, ('Alpha Fix', 'NodeSocketFloat'))
    options = interface.new_panel(name='Options', default_closed=True)
    option_names = {'Alpha Fix', 'Object Space'}
    for name, socket_type in input_sockets:
        socket = interface.new_socket(name=name, in_out='INPUT', socket_type=socket_type, parent=options if name in option_names else None)
        if name in {'Alpha', 'Alpha Fix'}:
            socket.default_value = 1.0 if name == 'Alpha' else 0.0
            socket.min_value = 0.0
            socket.max_value = 1.0
            socket.subtype = 'FACTOR'
        elif name == 'Bump Scale':
            socket.description = 'Control bump detail derived from image brightness. Negative values reverse the bumps. Zero disables the effect.'
            socket.default_value = 0.0
            socket.min_value = -10000.0
            socket.max_value = 10000.0
        elif name == 'Normal':
            socket.default_value = (0.5, 0.5, 1.0, 1.0)
        elif name == 'Normal Scale':
            socket.description = 'Control the strength of surface detail from the normal map.'
            socket.default_value = 1.0
            socket.min_value = 0.0
            socket.max_value = 10.0
        elif name == 'Object Space':
            socket.description = 'Interpret the normal map in object space when enabled, or tangent space when disabled.'
            socket.default_value = False
        if name == 'Alpha Fix':
            socket.description = 'Reduce semi-transparent fringes around image edges. Higher values remove more faint edge pixels. Zero keeps the original transparency.'
    output_sockets = [('Color', 'NodeSocketColor'), ('Roughness', 'NodeSocketFloat'), ('Alpha', 'NodeSocketFloat'), ('Normal', 'NodeSocketVector')]
    for name, socket_type in output_sockets:
        interface.new_socket(name=name, in_out='OUTPUT', socket_type=socket_type)
    nodes, links = group.nodes, group.links
    group_input, group_output, roughness_curve, bump = build_material_nodes(group)
    normal_attribute = nodes.new('ShaderNodeAttribute')
    normal_attribute.attribute_type = 'GEOMETRY'
    normal_attribute.attribute_name = NORMAL_REDUCTION_ATTRIBUTE_NAME
    normal_weight = nodes.new('ShaderNodeMath')
    normal_weight.operation = 'SUBTRACT'
    normal_weight.inputs[0].default_value = 1.0
    links.new(normal_attribute.outputs['Fac'], normal_weight.inputs[1])
    weighted_strength = nodes.new('ShaderNodeMath')
    weighted_strength.operation = 'MULTIPLY'
    links.new(group_input.outputs['Normal Scale'], weighted_strength.inputs[0])
    links.new(normal_weight.outputs[0], weighted_strength.inputs[1])
    tangent_normal = nodes.new('ShaderNodeNormalMap')
    tangent_normal.space = 'TANGENT'
    object_normal = nodes.new('ShaderNodeNormalMap')
    object_normal.space = 'OBJECT'
    choose_normal = nodes.new('ShaderNodeMix')
    choose_normal.data_type = 'VECTOR'
    links.new(group_input.outputs['Normal'], tangent_normal.inputs['Color'])
    links.new(weighted_strength.outputs[0], tangent_normal.inputs['Strength'])
    normal_color, normal_strength = transform_object_normal_color(
        group, group_input.outputs['Normal'], weighted_strength.outputs[0],
    )
    links.new(normal_color, object_normal.inputs['Color'])
    links.new(normal_strength, object_normal.inputs['Strength'])
    links.new(group_input.outputs['Object Space'], choose_normal.inputs[0])
    links.new(tangent_normal.outputs['Normal'], choose_normal.inputs[4])
    links.new(object_normal.outputs['Normal'], choose_normal.inputs[5])
    links.new(choose_normal.outputs['Result'], bump.inputs['Normal'])
    processed_alpha = group_input.outputs['Alpha']
    alpha_curve = nodes.new('ShaderNodeFloatCurve')
    alpha_curve.mapping.initialize()
    alpha_curve.mapping.extend = 'HORIZONTAL'
    alpha_curve.mapping.use_clip = True
    alpha_points = alpha_curve.mapping.curves[0].points
    alpha_points[0].location = (0.0, 0.0)
    alpha_points[-1].location = (1.0, 1.0)
    alpha_points.new(0.8, 0.0)
    alpha_points.new(0.925, 0.925)
    for point in alpha_points:
        point.handle_type = 'AUTO_CLAMPED'
    alpha_curve.mapping.update()
    links.new(group_input.outputs['Alpha'], alpha_curve.inputs['Value'])
    links.new(group_input.outputs['Alpha Fix'], alpha_curve.inputs['Factor'])
    processed_alpha = alpha_curve.outputs['Value']
    connect_material_outputs(group, group_input, group_output, roughness_curve, bump, processed_alpha)
    group.color_tag = 'SHADER'
    group.description = f'Prepare {group_name} material outputs.'
    group.use_fake_user = True
    for node in nodes:
        for socket in node.outputs:
            socket.hide = not socket.is_linked
    return group
