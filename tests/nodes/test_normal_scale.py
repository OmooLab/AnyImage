"""Render optional geometry weights against ordinary normal map strength."""
import bpy
import numpy as np
import pytest

from anyimage.operators.cutout_tool.shape import NORMAL_REDUCTION_ATTRIBUTE_NAME
from tests.support.materials import image_layer


@pytest.mark.parametrize('engine', ['CYCLES', 'BLENDER_EEVEE_NEXT'])
@pytest.mark.parametrize('domain', ['POINT', 'FACE'])
def test_normal_scale_preserves_missing_and_zero_weights(image_layer, engine, domain, tmp_path):
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 320, 64
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.filepath = str(tmp_path / 'normal_scale.exr')
    bpy.ops.object.camera_add(location=(0, 0, 10))
    scene.camera = bpy.context.object
    scene.camera.data.type = 'ORTHO'
    scene.camera.data.ortho_scale = 10
    for mode_index, space in enumerate(('TANGENT',)):
        shared = None
        for weight_index, weight in enumerate((None, 0.0, 0.4, 1.0, 2.0)):
            column = mode_index * 5 + weight_index
            for reference in (False, True):
                bpy.ops.mesh.primitive_plane_add(
                    size=.8, location=(column - 4.5, .5 if reference else -.5, 0),
                )
                obj = bpy.context.object
                obj.data.uv_layers.active.name = 'UVMap'
                if weight is not None and not reference:
                    attr = obj.data.attributes.new(NORMAL_REDUCTION_ATTRIBUTE_NAME, 'FLOAT', domain)
                    for item in attr.data:
                        item.value = 1.0 - weight
                if not reference and shared is not None:
                    obj.data.materials.append(shared)
                    continue
                material = bpy.data.materials.new(f'{space} {weight} {reference}')
                material.use_nodes = True
                nodes, links = material.node_tree.nodes, material.node_tree.links
                nodes.clear()
                normal = nodes.new('ShaderNodeNormalMap' if reference else 'ShaderNodeGroup')
                color = (.7, .65, .9, 1)
                if reference:
                    normal.space = space
                    normal.inputs['Color'].default_value = color
                    normal.inputs['Strength'].default_value = .5 * (1 if weight is None else weight)
                else:
                    normal.node_tree = image_layer
                    normal.inputs['Object Space'].default_value = space == 'OBJECT'
                    normal.inputs['Normal'].default_value = color
                    normal.inputs['Normal Scale'].default_value = .5
                    shared = material
                encode = nodes.new('ShaderNodeVectorMath')
                encode.operation = 'MULTIPLY_ADD'
                encode.inputs[1].default_value = (.5, .5, .5)
                encode.inputs[2].default_value = (.5, .5, .5)
                links.new(normal.outputs['Normal'], encode.inputs[0])
                emission = nodes.new('ShaderNodeEmission')
                output = nodes.new('ShaderNodeOutputMaterial')
                links.new(encode.outputs[0], emission.inputs['Color'])
                links.new(emission.outputs[0], output.inputs['Surface'])
                obj.data.materials.append(material)
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
    try:
        pixels = np.array(rendered.pixels[:]).reshape(64, 320, 4)
        columns = np.arange(5) * 32 + 16
        np.testing.assert_allclose(pixels[16, columns, :3], pixels[48, columns, :3], atol=2e-4)
        assert np.linalg.norm(pixels[16, 16, :3] - pixels[16, 48, :3]) > .01
    finally:
        bpy.data.images.remove(rendered)
