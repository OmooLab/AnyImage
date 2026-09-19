"""Build O Image Depth Layer."""
import bpy
from anyimage.common.material import DEPTH_MATERIAL_NODE_GROUP_NAME
from ..common.shader import build_material_nodes, connect_material_outputs

MATERIAL_DISPLACEMENT_ATTRIBUTE = "o_material_displacement"
BACKGROUND_DEPTH_ATTRIBUTE = "o_background_depth"
DEPTH_SCALE_ATTRIBUTE = "o_depth_scale"


def build_image_depth_layer_group():
    group_name = DEPTH_MATERIAL_NODE_GROUP_NAME
    existing = bpy.data.node_groups.get(group_name)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    interface = group.interface
    input_sockets = [('Color', 'NodeSocketColor'), ('Alpha', 'NodeSocketFloat'), ('Bump Scale', 'NodeSocketFloat')]
    input_sockets.insert(2, ('Depth', 'NodeSocketFloat'))
    options = None
    option_names = {'Alpha Fix', 'Normal Scale', 'Object Space'}
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
            socket.default_value = 1.0
            socket.min_value = 0.0
            socket.max_value = 10.0
        elif name == 'Object Space':
            socket.default_value = False
    output_sockets = [('Color', 'NodeSocketColor'), ('Roughness', 'NodeSocketFloat'), ('Alpha', 'NodeSocketFloat'), ('Normal', 'NodeSocketVector')]
    output_sockets.append(('Displacement', 'NodeSocketVector'))
    for name, socket_type in output_sockets:
        interface.new_socket(name=name, in_out='OUTPUT', socket_type=socket_type)
    nodes, links = group.nodes, group.links
    group_input, group_output, roughness_curve, bump = build_material_nodes(group)
    processed_alpha = group_input.outputs['Alpha']
    displacement = nodes.new('ShaderNodeDisplacement')
    displacement.inputs['Midlevel'].default_value = 0.0
    displacement.inputs['Scale'].default_value = 1.0
    background_attribute = nodes.new('ShaderNodeAttribute')
    background_attribute.attribute_type = 'GEOMETRY'
    background_attribute.attribute_name = BACKGROUND_DEPTH_ATTRIBUTE
    material_attribute = nodes.new('ShaderNodeAttribute')
    material_attribute.attribute_type = 'GEOMETRY'
    material_attribute.attribute_name = MATERIAL_DISPLACEMENT_ATTRIBUTE
    strength_attribute = nodes.new('ShaderNodeAttribute')
    strength_attribute.attribute_type = 'GEOMETRY'
    strength_attribute.attribute_name = DEPTH_SCALE_ATTRIBUTE
    foreground_mask = nodes.new('ShaderNodeMath')
    foreground_mask.operation = 'GREATER_THAN'
    foreground_mask.inputs[1].default_value = 0.5
    clamp_foreground = nodes.new('ShaderNodeMath')
    clamp_foreground.operation = 'MAXIMUM'
    masked_depth = nodes.new('ShaderNodeMix')
    masked_depth.data_type = 'FLOAT'
    enabled_depth = nodes.new('ShaderNodeMath')
    enabled_depth.operation = 'MULTIPLY'
    scaled_depth = nodes.new('ShaderNodeMath')
    scaled_depth.operation = 'MULTIPLY'
    links.new(group_input.outputs['Alpha'], foreground_mask.inputs[0])
    links.new(group_input.outputs['Depth'], clamp_foreground.inputs[0])
    links.new(background_attribute.outputs['Fac'], clamp_foreground.inputs[1])
    links.new(foreground_mask.outputs[0], masked_depth.inputs[0])
    links.new(background_attribute.outputs['Fac'], masked_depth.inputs[2])
    links.new(clamp_foreground.outputs[0], masked_depth.inputs[3])
    links.new(masked_depth.outputs['Result'], enabled_depth.inputs[0])
    links.new(material_attribute.outputs['Fac'], enabled_depth.inputs[1])
    links.new(enabled_depth.outputs[0], scaled_depth.inputs[0])
    links.new(strength_attribute.outputs['Fac'], scaled_depth.inputs[1])
    processed_alpha = foreground_mask.outputs[0]
    processed_depth = scaled_depth.outputs[0]
    connect_material_outputs(group, group_input, group_output, roughness_curve, bump, processed_alpha)
    links.new(processed_depth, displacement.inputs['Height'])
    links.new(displacement.outputs['Displacement'], group_output.inputs['Displacement'])
    group.color_tag = 'SHADER'
    group.description = 'Prepare image depth material outputs.'
    group.use_fake_user = True
    return group
