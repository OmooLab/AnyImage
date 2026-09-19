"""Share persistent face attributes between depth symmetry and image materials.

Rotation stores pre-inversion Euler angles, face kind is 1/2/3 for front/back/wall,
and axis is 1 for the final +X orientation. Missing attributes mean identity.
These FACE attributes stay on the output mesh for the material consumer.
"""
from mathutils import Matrix

from anyimage.common.object import blender_frame_rotation

ROTATION_ATTRIBUTE = 'o_depth_rotation'
FACE_ATTRIBUTE = 'o_depth_face'
AXIS_ATTRIBUTE = 'o_depth_axis'


def transform_object_normal_color(group, color, strength):
    """Rotate encoded object normals, reflect backs and disable wall normal maps."""
    nodes, links = group.nodes, group.links

    def attribute(name):
        node = nodes.new('ShaderNodeAttribute')
        node.attribute_type = 'GEOMETRY'
        node.attribute_name = name
        return node

    def math(operation, value, constant):
        node = nodes.new('ShaderNodeMath')
        node.operation = operation
        links.new(value, node.inputs[0])
        node.inputs[1].default_value = constant
        return node.outputs[0]

    rotation = attribute(ROTATION_ATTRIBUTE)
    face = attribute(FACE_ATTRIBUTE)
    axis = attribute(AXIS_ATTRIBUTE)
    decode = nodes.new('ShaderNodeVectorMath')
    decode.operation = 'MULTIPLY_ADD'
    decode.inputs[1].default_value = (2., 2., 2.)
    decode.inputs[2].default_value = (-1., -1., -1.)
    links.new(color, decode.inputs[0])
    base = nodes.new('ShaderNodeVectorRotate')
    base.rotation_type = 'EULER_XYZ'
    base.inputs['Rotation'].default_value = Matrix(blender_frame_rotation()).to_euler()
    links.new(decode.outputs[0], base.inputs['Vector'])
    rotate = nodes.new('ShaderNodeVectorRotate')
    rotate.rotation_type = 'EULER_XYZ'
    rotate.invert = True
    links.new(base.outputs[0], rotate.inputs['Vector'])
    links.new(rotation.outputs['Vector'], rotate.inputs['Rotation'])
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(rotate.outputs[0], separate.inputs[0])
    back = math('COMPARE', face.outputs['Fac'], 2.)
    # Reflect the normal's Y component on the back.
    difference = math('MULTIPLY', separate.outputs['Y'], -2.)
    correction = nodes.new('ShaderNodeMath')
    correction.operation = 'MULTIPLY_ADD'
    links.new(back, correction.inputs[0])
    links.new(difference, correction.inputs[1])
    links.new(separate.outputs['Y'], correction.inputs[2])
    combine = nodes.new('ShaderNodeCombineXYZ')
    links.new(separate.outputs['X'], combine.inputs['X'])
    links.new(correction.outputs[0], combine.inputs['Y'])
    links.new(separate.outputs['Z'], combine.inputs['Z'])
    axis_rotation = nodes.new('ShaderNodeVectorMath')
    axis_rotation.operation = 'SCALE'
    axis_rotation.inputs[0].default_value = Matrix.Rotation(1.5707963267948966, 4, 'Z').to_euler()
    links.new(axis.outputs['Fac'], axis_rotation.inputs['Scale'])
    orient = nodes.new('ShaderNodeVectorRotate')
    orient.rotation_type = 'EULER_XYZ'
    links.new(combine.outputs[0], orient.inputs['Vector'])
    links.new(axis_rotation.outputs[0], orient.inputs['Rotation'])
    encode = nodes.new('ShaderNodeVectorMath')
    encode.operation = 'MULTIPLY_ADD'
    encode.inputs[1].default_value = (.5, .5, .5)
    encode.inputs[2].default_value = (.5, .5, .5)
    links.new(orient.outputs[0], encode.inputs[0])
    mapped = math('LESS_THAN', face.outputs['Fac'], 2.5)
    weight = nodes.new('ShaderNodeMath')
    weight.operation = 'MULTIPLY'
    links.new(mapped, weight.inputs[0])
    links.new(strength, weight.inputs[1])
    return encode.outputs[0], weight.outputs[0]
