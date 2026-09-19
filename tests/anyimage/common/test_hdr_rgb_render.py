import bpy
import numpy as np
import pytest

from anyimage.common.hdr_image import HdrBackgroundInput
from anyimage.common.image import cleanup_image_input, image_rgba
from anyimage.common.image_target import ImageEditTarget
from tests.support.hdr_image import hdr_texture
from tests.support.image_texture import texture, texture_context


@pytest.mark.parametrize("use_alpha", [False, True])
def test_hdr_texture_rgb_remains_visible_independently_of_alpha(hdr_texture, tmp_path, use_alpha):
    source = hdr_texture.image
    source.pixels.foreach_set(np.tile([4, 2, 0.5, 1], 12).astype(np.float32))
    alpha = np.tile([0, 0.25, 0.5, 1], (3, 1)).astype(np.float32)
    path = tmp_path / "alpha.npy"
    np.save(path, alpha)
    snapshot = HdrBackgroundInput.prepare(source)
    try:
        result = snapshot.apply(ImageEditTarget.capture(texture_context(hdr_texture)), path)
    finally:
        cleanup_image_input(snapshot.path, True)

    # A second removal must accept its own independent-channel result and keep RGB intact.
    snapshot = HdrBackgroundInput.prepare(result)
    try:
        snapshot.apply(ImageEditTarget.capture(texture_context(hdr_texture)), path)
        np.testing.assert_array_equal(image_rgba(result)[..., :3], np.tile([4, 2, 0.5], (3, 4, 1)))
    finally:
        cleanup_image_input(snapshot.path, True)
    result.reload()

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = False
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = 64, 16
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.filepath = str(tmp_path / "render.exr")
    bpy.ops.object.camera_add(location=(0, 0, 5))
    scene.camera = bpy.context.object
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 4
    bpy.ops.mesh.primitive_plane_add(size=2)
    bpy.context.object.scale = (2, 0.5, 1)
    material = bpy.data.materials.new("HDR RGB validation")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = result
    image_node.interpolation = "Closest"
    emission = nodes.new("ShaderNodeEmission")
    links.new(image_node.outputs["Color"], emission.inputs["Color"])
    output = nodes.new("ShaderNodeOutputMaterial")
    if use_alpha:
        transparent = nodes.new("ShaderNodeBsdfTransparent")
        mix = nodes.new("ShaderNodeMixShader")
        links.new(image_node.outputs["Alpha"], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs["Surface"])
    else:
        links.new(emission.outputs[0], output.inputs["Surface"])
    bpy.context.object.data.materials.append(material)
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
    pixels = image_rgba(rendered)
    for index, opacity in enumerate((0, 0.0625, 0.25, 1)):
        patch = pixels[4:12, index * 16 + 4:index * 16 + 12]
        expected_alpha = opacity if use_alpha else 1
        np.testing.assert_allclose(patch[..., 3].mean(), expected_alpha, atol=0.035)
        expected_rgb = patch[..., 3:4] * np.array([4, 2, 0.5])
        np.testing.assert_allclose(patch[..., :3], expected_rgb, rtol=2e-5, atol=1e-6)
