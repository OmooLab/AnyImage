"""Render environment directions and verify rotation-only object tracking."""

import bpy
import numpy as np
from mathutils import Euler, Vector

from anyimage.common.image import image_rgba
from anyimage.operators.convert_to_panorama.world import create_panorama_world


def test_environment_tracks_world_rotation_without_translation_or_scale(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = bpy.data.objects.new("Panorama", None)
    bpy.context.collection.objects.link(obj)
    image = bpy.data.images.new("Direction colors", width=256, height=128, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    u, v = np.meshgrid((np.arange(256) + .5) / 256, (np.arange(128) + .5) / 128)
    longitude, latitude = np.pi - 2 * np.pi * u, np.pi * (v - .5)
    rgba = np.ones((128, 256, 4), np.float32)
    rgba[..., :3] = np.stack((np.cos(latitude) * np.cos(longitude),
                              np.cos(latitude) * np.sin(longitude), np.sin(latitude)), axis=-1) * .5 + .5
    image.pixels.foreach_set(rgba.ravel())
    image.pack()
    scene = bpy.context.scene
    scene.world = create_panorama_world(obj, image)
    nodes = scene.world.node_tree.nodes
    texture = next(node for node in nodes if node.type == "TEX_ENVIRONMENT")
    background = next(node for node in nodes if node.type == "GROUP")
    # Expose the lighting texture to camera rays for direction comparison.
    scene.world.node_tree.links.new(texture.outputs["Color"], background.inputs["Color"])
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    bpy.context.collection.objects.link(camera)
    camera.data.lens = 100
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 8
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    local_ray = Vector((.3, -.8, .5)).normalized()

    def render(index):
        bpy.context.view_layer.update()
        rotation = obj.matrix_world.to_quaternion()
        camera.rotation_euler = (rotation @ local_ray).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(tmp_path / f"world-{index}.exr")
        bpy.ops.render.render(write_still=True)
        result = bpy.data.images.load(scene.render.filepath, check_existing=False)
        try:
            return image_rgba(result)[..., :3].mean(axis=(0, 1))
        finally:
            bpy.data.images.remove(result)

    baseline = render(0)
    np.testing.assert_allclose(baseline, np.array(local_ray) * .5 + .5, atol=.015)
    obj.rotation_euler = (.4, -.6, .8)
    np.testing.assert_allclose(render(1), baseline, atol=.015)
    obj.location = (80, -110, 200)
    obj.scale = (2, 3, 4)
    camera.location = (-50, 40, 15)
    np.testing.assert_allclose(render(2), baseline, atol=.015)
    parent = bpy.data.objects.new("Parent", None)
    bpy.context.collection.objects.link(parent)
    parent.rotation_euler = (-.3, .7, -.2)
    parent.location = (10, 20, -30)
    obj.parent = parent
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Euler((.2, -.5, .9)).to_quaternion()
    np.testing.assert_allclose(render(3), baseline, atol=.015)
    # Drivers and their object targets must survive saving and reopening.
    blend = tmp_path / "panorama-world.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    obj = bpy.data.objects["Panorama"]
    scene = bpy.context.scene
    camera = scene.camera
    obj.rotation_quaternion = Euler((-.7, .2, -.4)).to_quaternion()
    np.testing.assert_allclose(render(4), baseline, atol=.015)
