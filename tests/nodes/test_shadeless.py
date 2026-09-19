"""Render the bundled Shadeless group's opacity and HDR color endpoints."""

import bpy
import addon_utils
import numpy as np

from anyimage.common.node import load_node_group


def test_shadeless_alpha_is_mixed_inside_the_group(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=False)
    group = load_node_group("O Shadeless")
    inputs = {s.name: s for s in group.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"}
    assert list(inputs) == ["Color", "Alpha", "Strength"]
    assert inputs["Alpha"].default_value == 1 and inputs["Strength"].default_value == 1
    assert inputs["Strength"].min_value == 0
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = 128, 32
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.filepath = str(tmp_path / "shadeless.exr")
    bpy.ops.object.camera_add(location=(0, 0, 5))
    scene.camera = bpy.context.object
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 4
    for index, (alpha, strength) in enumerate(((0, 1), (0.5, 1), (1, 1), (1, 2))):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(index - 1.5, 0, 0))
        material = bpy.data.materials.new(f"Alpha {alpha} Strength {strength}")
        material.use_nodes = True
        material.node_tree.nodes.clear()
        shader = material.node_tree.nodes.new("ShaderNodeGroup")
        shader.node_tree = group
        shader.inputs["Color"].default_value = (4, 2, 0.5, 1)
        shader.inputs["Alpha"].default_value = alpha
        shader.inputs["Strength"].default_value = strength
        output = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(shader.outputs[0], output.inputs["Surface"])
        bpy.context.object.data.materials.append(material)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(scene.render.filepath, check_existing=False)
    try:
        pixels = np.array(image.pixels[:]).reshape(32, 128, 4)
        for index, alpha in enumerate((0, 0.5, 1, 1)):
            patch = pixels[8:24, index * 32 + 8:index * 32 + 24]
            np.testing.assert_allclose(patch[..., 3].mean(), alpha, atol=0.035)
        np.testing.assert_allclose(pixels[16, 80, :3], (4, 2, 0.5), atol=1e-4)
        np.testing.assert_allclose(pixels[16, 112, :3], (8, 4, 1), atol=1e-4)
    finally:
        bpy.data.images.remove(image)
        bpy.ops.wm.read_factory_settings(use_empty=True)
