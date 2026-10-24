"""Verify panorama probe bounds, parenting and isolated baking."""

from types import SimpleNamespace
from itertools import product
import bpy
import numpy as np
import pytest
from mathutils import Vector

from anyimage.operators.convert_to_panorama import light_probe
from anyimage import ai_preferences as preferences


@pytest.fixture
def panorama():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    return bpy.context.object


@pytest.mark.parametrize("lower,upper,limit,size,resolution,center", [
    ((-1.6, -1.25, -10.3), (1.6, 1.25, 35), 20, (4, 3, 31), (3, 2, 30), (0, 0, 4.5)),
    ((-20, -20, -20), (20, 20, 20), 20, (40, 40, 40), (40, 40, 40), (0, 0, 0)),
    ((-1.5, -1, -15), (1.5, 1, 15), 20, (3, 2, 30), (3, 2, 30), (0, 0, 0)),
    ((0, 0, 0), (.2, .5, 0), 20, (1, 1, 1), (1, 1, 1), (.1, .25, 0)),
    ((-30, -30, -30), (30, 30, 30), 20.2, (40.4, 40.4, 40.4), (40, 40, 40), (0, 0, 0)),
    ((-300, -300, -300), (300, 300, 300), 300, (600, 600, 600), (256, 256, 256), (0, 0, 0)),
])
def test_probe_bounds(panorama, lower, upper, limit, size, resolution, center):
    for vertex in panorama.data.vertices:
        vertex.co = [upper[i] if vertex.co[i] > 0 else lower[i] for i in range(3)]
    panorama.data.update()
    bpy.context.view_layer.update()
    result = light_probe.panorama_probe_bounds(bpy.context, panorama, limit)
    np.testing.assert_allclose(result[0], center, atol=1e-5)
    np.testing.assert_allclose(result[1], size)
    assert tuple(result[2]) == resolution


def test_parent_and_units(panorama):
    bpy.context.scene.unit_settings.scale_length = .01
    panorama.location = (100, 200, 300)
    panorama.scale = (-160, 125, 1515)
    bpy.context.view_layer.update()
    probe = light_probe.create_panorama_light_probe(bpy.context, panorama, 20)
    bpy.context.view_layer.update()
    assert probe.parent == panorama
    np.testing.assert_allclose(probe.matrix_world.translation, panorama.location)
    np.testing.assert_allclose(probe.matrix_world.to_scale() * 2, (400, 300, 3100))
    # Volume capture uses the local [-1, 1] cube; Object.bound_box is unavailable.
    corners = np.array([probe.matrix_world @ Vector(corner) for corner in product((-1, 1), repeat=3)])
    np.testing.assert_allclose(corners.max(axis=0) - corners.min(axis=0), (400, 300, 3100))
    assert (probe.data.resolution_x, probe.data.resolution_y, probe.data.resolution_z) == (3, 2, 30)
    assert not probe.data.capture_indirect and probe.data.capture_emission and not probe.data.capture_world
    assert probe.data.clamp_direct == 50.0
    before = probe.matrix_world.translation.copy()
    panorama.location.x += 10
    bpy.context.view_layer.update()
    np.testing.assert_allclose(probe.matrix_world.translation, before + Vector((10, 0, 0)))


def test_empty_and_outside_region(panorama):
    for vertex in panorama.data.vertices:
        vertex.co.x += 100
    panorama.data.update()
    assert light_probe.create_panorama_light_probe(bpy.context, panorama, 20) is None
    panorama.data.clear_geometry()
    assert light_probe.create_panorama_light_probe(bpy.context, panorama, 20) is None


def test_default_and_disabled_preferences(monkeypatch):
    monkeypatch.setattr(preferences, "addon_preferences", lambda _: None)
    assert preferences.configured_panorama_light_probe() == (True, 20)
    monkeypatch.setattr(preferences, "addon_preferences", lambda _: SimpleNamespace(
        panorama_light_probe_enabled=False, panorama_light_probe_max_distance=.1))
    assert preferences.configured_panorama_light_probe() == (False, .5)


@pytest.mark.parametrize("outcome", [{"FINISHED"}, {"CANCELLED"}, RuntimeError("Bake failed")])
def test_bake_restores_scene(panorama, monkeypatch, outcome):
    probe = light_probe.create_panorama_light_probe(bpy.context, panorama, 20)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    bpy.context.scene.render.engine = "CYCLES"
    panorama.hide_probe_volume = True
    def bake(*args, **kwargs):
        assert sun.hide_render and not panorama.hide_render
        assert not panorama.hide_probe_volume
        assert bpy.context.object == probe
        assert args == ("EXEC_DEFAULT",) and kwargs == {"subset": "ACTIVE"}
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(light_probe, "bpy", SimpleNamespace(ops=SimpleNamespace(
        object=SimpleNamespace(lightprobe_cache_bake=bake))))
    if outcome == {"FINISHED"}:
        light_probe.bake_panorama_light_probe(bpy.context, panorama, probe)
    else:
        with pytest.raises(RuntimeError):
            light_probe.bake_panorama_light_probe(bpy.context, panorama, probe)
    assert not sun.hide_render and panorama.hide_probe_volume
    assert bpy.context.object == sun and sun.select_get() and not probe.select_get()
    assert bpy.context.scene.render.engine == "CYCLES"


@pytest.mark.parametrize("engine", ["BLENDER_EEVEE_NEXT"])
def test_real_bake_ignores_external_objects(panorama, tmp_path, engine):
    panorama.scale = (2, 2, 2)
    material = bpy.data.materials.new("Panorama emission")
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Emission Color"].default_value = (1, .2, .1, 1)
    shader.inputs["Emission Strength"].default_value = 2
    panorama.data.materials.append(material)
    bpy.context.view_layer.update()
    probe = light_probe.create_panorama_light_probe(bpy.context, panorama, 20)
    probe.data.resolution_x = probe.data.resolution_y = probe.data.resolution_z = 2
    probe.data.bake_samples = 16
    probe.data.surfel_density = 4
    probe.data.validity_threshold = 0
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.world = None
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=.3)
    bpy.ops.object.camera_add(location=(0, 0, 1))
    scene.camera = bpy.context.object
    scene.render.resolution_x = scene.render.resolution_y = 16
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    def render(name):
        panorama.hide_render = True
        scene.render.filepath = str(tmp_path / f"{name}.exr")
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = np.array(image.pixels[:])
        bpy.data.images.remove(image)
        panorama.hide_render = False
        return pixels
    unbaked = render("unbaked")
    light_probe.bake_panorama_light_probe(bpy.context, panorama, probe)
    baseline = render("baseline")
    assert np.max(abs(baseline - unbaked)) > .01
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 100
    bpy.ops.mesh.primitive_cube_add(size=1)
    blocker = bpy.context.object
    blocker.data.materials.append(material)
    collection = bpy.data.collections.new("External instances")
    collection.objects.link(blocker)
    instance = bpy.data.objects.new("Instance", None)
    instance.instance_type = "COLLECTION"
    instance.instance_collection = collection
    scene.collection.objects.link(instance)
    light_probe.bake_panorama_light_probe(bpy.context, panorama, probe)
    assert all(not obj.hide_render for obj in (sun, blocker, instance))
    for obj in (sun, blocker, instance):
        obj.hide_render = True
    contaminated = render("isolated")
    np.testing.assert_allclose(contaminated, baseline, atol=1e-4)
    second = light_probe.create_panorama_light_probe(bpy.context, panorama, 20)
    second.data.resolution_x = second.data.resolution_y = second.data.resolution_z = 1
    second.data.bake_samples = 16
    second.data.surfel_density = 4
    shader.inputs["Emission Color"].default_value = (0, 1, 0, 1)
    light_probe.bake_panorama_light_probe(bpy.context, panorama, second)
    second.hide_render = True
    np.testing.assert_allclose(render("preserved"), baseline, atol=1e-4)
