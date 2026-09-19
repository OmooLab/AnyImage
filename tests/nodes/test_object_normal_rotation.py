"""Render the image material's object normals from persistent geometry attributes."""
import bpy
import numpy as np
import pytest
from mathutils import Euler, Vector, Matrix

from tests.support.materials import image_layer
from anyimage.common.object import blender_frame_rotation
from nodes.common.normal_map import ROTATION_ATTRIBUTE, FACE_ATTRIBUTE, AXIS_ATTRIBUTE


SYMMETRY_Y_TO_X = Matrix.Rotation(1.5707963267948966, 4, "Z").to_3x3()


@pytest.mark.parametrize('engine', ['CYCLES', 'BLENDER_EEVEE_NEXT'])
def test_object_normals_follow_rotation_mirror_axis_and_wall_mask(image_layer, engine, tmp_path):
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 224, 32
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.filepath = str(tmp_path / 'normals.exr')
    bpy.ops.object.camera_add(location=(0, 0, 10))
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 7
    scene.camera = camera
    normal = Vector((.2, .3, .9)).normalized()
    rotation = Euler((.25, -.4, .15))
    expected = []
    # Missing attributes, front, back, wall, final axis, zero strength, tangent.
    cases = [(0, 0, 1, True), (1, 0, 1, True), (2, 0, 1, True),
             (3, 0, 1, True), (1, 1, 1, True), (1, 0, 0, True), (1, 0, 1, False)]
    for index, (face, axis, strength, object_space) in enumerate(cases):
        bpy.ops.mesh.primitive_plane_add(size=.9, location=(index - 3, 0, 0))
        obj = bpy.context.object
        obj.data.uv_layers.active.name = 'UVMap'
        if face:
            attr = obj.data.attributes.new(ROTATION_ATTRIBUTE, 'FLOAT_VECTOR', 'FACE')
            for item in attr.data:
                item.vector = rotation
            for name, value in ((FACE_ATTRIBUTE, face), (AXIS_ATTRIBUTE, axis)):
                attr = obj.data.attributes.new(name, 'FLOAT', 'FACE')
                for item in attr.data:
                    item.value = value
        material = bpy.data.materials.new(f'Normal {index}')
        material.use_nodes = True
        nodes, links = material.node_tree.nodes, material.node_tree.links
        nodes.clear()
        layer = nodes.new('ShaderNodeGroup')
        layer.node_tree = image_layer
        layer.inputs['Object Space'].default_value = object_space
        layer.inputs['Normal Scale'].default_value = strength
        layer.inputs['Normal'].default_value = (*((np.array(normal) + 1) / 2), 1)
        encode = nodes.new('ShaderNodeVectorMath')
        encode.operation = 'MULTIPLY_ADD'
        encode.inputs[1].default_value = (.5, .5, .5)
        encode.inputs[2].default_value = (.5, .5, .5)
        links.new(layer.outputs['Normal'], encode.inputs[0])
        emission = nodes.new('ShaderNodeEmission')
        output = nodes.new('ShaderNodeOutputMaterial')
        links.new(encode.outputs[0], emission.inputs['Color'])
        links.new(emission.outputs[0], output.inputs['Surface'])
        obj.data.materials.append(material)
        value = normal.copy()
        if object_space:
            value = Matrix(blender_frame_rotation()).to_3x3() @ value
        if face and object_space:
            value = rotation.to_matrix().transposed() @ value
            if face == 2:
                value.y *= -1
            if axis:
                value = SYMMETRY_Y_TO_X @ value
        if strength == 0 or face == 3:
            value = Vector((0, 0, 1))
        expected.append((np.array(value) + 1) / 2)
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
    try:
        pixels = np.array(rendered.pixels[:]).reshape(32, 224, 4)
        np.testing.assert_allclose(
            pixels[16, np.arange(7) * 32 + 16, :3], expected,
            atol=1e-3 if engine == 'BLENDER_EEVEE_NEXT' else 2e-4,
        )
    finally:
        bpy.data.images.remove(rendered)
