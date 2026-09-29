"""Verify static texture conversion, source isolation and attribute cleanup."""

import bpy
import numpy as np
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from anyimage.common.material import create_image_material
from anyimage.common.object import modifier_input_identifier, set_modifier_input
from anyimage.operators.convert_to_mesh.materialization import build_conversion_mesh, PROTOCOL_ATTRIBUTES
from anyimage.operators.convert_to_mesh import ConvertToMesh
from nodes.groups.image_cutout import build_image_cutout_group
from nodes.groups.image_layer import build_image_layer_group
from mathutils import Vector
from tests.nodes.test_cutout_symmetry import symmetry


@pytest.fixture
def cutout():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_image_layer_group()
    mesh = bpy.data.meshes.new("Cutout")
    mesh.from_pydata([(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for item, value in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        item.uv = value
    mesh.attributes.new("user_value", "FLOAT", "POINT").data.foreach_set("value", [1, 2, 3, 4])
    color = bpy.data.images.new("Color", width=64, height=64, alpha=True, float_buffer=True)
    color.colorspace_settings.name = "Non-Color"
    pixels = np.ones((64, 64, 4), dtype=np.float32)
    pixels[..., 0] = np.linspace(0, 2, 64)[None, :]
    pixels[..., 1] = .2
    color.pixels.foreach_set(pixels.ravel())
    normal = bpy.data.images.new("Normal", width=64, height=64, float_buffer=True)
    normal.colorspace_settings.name = "Non-Color"
    normal.pixels.foreach_set(np.tile(np.array([.7, .6, .95, 1], dtype=np.float32), 64 * 64))
    material = create_image_material(color, color, normal_image=normal)
    mesh.materials.append(material)
    obj = bpy.data.objects.new("Cutout", mesh)
    obj["o_image_object"] = True
    bpy.context.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("Cutout", "NODES")
    modifier.node_group = build_image_cutout_group()
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Mode"), 1)
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"), .2)
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    yield obj
    bpy.ops.wm.read_factory_settings(use_empty=True)


def test_materialization_is_static_and_does_not_mutate_source(cutout):
    source_mesh = cutout.data
    source_material = cutout.active_material
    source_scene = bpy.context.window.scene
    source_selection = list(bpy.context.selected_objects)
    source_material.node_tree.nodes.new("ShaderNodeGroup")
    result = build_conversion_mesh(bpy.context, cutout)
    assert result is not None
    assert cutout.data == source_mesh and len(cutout.modifiers) == 1
    assert result.materials[0] != source_material
    assert not (set(result.attributes.keys()) & PROTOCOL_ATTRIBUTES)
    assert "user_value" in result.attributes
    assert list(result.uv_layers.keys()) == ["UVMap"]
    layer = next(n for n in result.materials[0].node_tree.nodes if n.type == "GROUP")
    assert layer.inputs["Object Space"].default_value is False
    assert layer.inputs["Normal Scale"].default_value == 1
    images = [n.image for n in result.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"]
    assert all(i.packed_file is not None for i in images)
    assert all(tuple(i.size) == (64, 128) for i in images)
    assert max(images[0].pixels[:]) > 1
    assert len(bpy.data.scenes) == 1
    assert bpy.context.window.scene == source_scene
    assert bpy.context.object == cutout and list(bpy.context.selected_objects) == source_selection
    assert not any(g.name.endswith('.001') for g in bpy.data.node_groups)


def visible_uv_coverage(obj, camera, resolution):
    """Classify visible pixels from geometric UV area, independently of shading."""
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.data
    mesh.calc_loop_triangles()
    uv = np.array([item.uv[:] for item in mesh.uv_layers["UVMap"].data])
    areas = np.zeros(len(mesh.polygons))
    for triangle in mesh.loop_triangles:
        a, b, c = uv[list(triangle.loops)]
        ab, ac = b - a, c - a
        areas[triangle.polygon_index] += abs(ab[0] * ac[1] - ab[1] * ac[0])
    camera_to_object = evaluated.matrix_world.inverted() @ camera.matrix_world
    direction = camera_to_object.to_3x3() @ Vector((0, 0, -1))
    coverage = np.full((resolution, resolution), -1, dtype=np.int8)
    for y in range(resolution):
        for x in range(resolution):
            local_x = ((x + .5) / resolution - .5) * camera.data.ortho_scale
            local_y = ((y + .5) / resolution - .5) * camera.data.ortho_scale
            origin = camera_to_object @ Vector((local_x, local_y, 0))
            hit, _, _, face = evaluated.ray_cast(origin, direction)
            if hit:
                coverage[y, x] = int(areas[face] > 1e-12)
    return coverage


def render_normal(obj, path, direction, *, lighting=False, with_uv_coverage=False):
    """Render the actual material normal as linear RGB for a comparison."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 64
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.filepath = str(path)
    camera_data = bpy.data.cameras.new("Probe")
    camera = bpy.data.objects.new("Probe", camera_data)
    scene.collection.objects.link(camera)
    camera.location = Vector(direction) * 5
    camera.rotation_euler = (-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 3
    scene.camera = camera
    materials = list(obj.data.materials)
    copies = [material.copy() for material in materials]
    for index, copy in enumerate(copies):
        obj.data.materials[index] = copy
        nodes, links = copy.node_tree.nodes, copy.node_tree.links
        layer = next(n for n in nodes if n.type == "GROUP")
        encode = nodes.new("ShaderNodeVectorMath")
        encode.operation = "MULTIPLY_ADD"
        encode.inputs[1].default_value = (.5, .5, .5)
        encode.inputs[2].default_value = (.5, .5, .5)
        emission = nodes.new("ShaderNodeEmission")
        output = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
        links.new(layer.outputs["Normal"], encode.inputs[0])
        links.new(encode.outputs[0], emission.inputs["Color"])
        if not lighting:
            links.new(emission.outputs[0], output.inputs["Surface"])
    light = None
    if lighting:
        light_data = bpy.data.lights.new("Probe light", "SUN")
        light = bpy.data.objects.new("Probe light", light_data)
        scene.collection.objects.link(light)
        light.rotation_euler = camera.rotation_euler
        light_data.energy = 2
    try:
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(str(path), check_existing=False)
        try:
            pixels = np.array(image.pixels[:]).reshape(64, 64, 4)
            return (pixels, visible_uv_coverage(obj, camera, 64)) if with_uv_coverage else pixels
        finally:
            bpy.data.images.remove(image)
    finally:
        for index, material in enumerate(materials):
            obj.data.materials[index] = material
        for copy in copies:
            bpy.data.materials.remove(copy)
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(camera_data)
        if light is not None:
            bpy.data.objects.remove(light, do_unlink=True)
            bpy.data.lights.remove(light_data)


@pytest.mark.parametrize("object_space", [False, True])
@pytest.mark.parametrize("bump", [0, .08])
@pytest.mark.parametrize("transformed", [False, True])
def test_static_normal_matches_shader_after_attributes_are_removed(cutout, tmp_path, object_space, bump, transformed):
    if transformed:
        cutout.rotation_euler = (.1, .2, .15)
        cutout.scale = (.8, 1.2, .9)
        bpy.context.view_layer.update()
    layer = next(n for n in cutout.active_material.node_tree.nodes if n.type == "GROUP")
    layer.inputs["Object Space"].default_value = object_space
    layer.inputs["Normal Scale"].default_value = .6
    layer.inputs["Bump Scale"].default_value = bump
    directions = ((0, -1, 0), (0, 1, 0), (1, -.2, 0))
    before = [render_normal(cutout, tmp_path / f"before-{i}.exr", d, with_uv_coverage=True) for i, d in enumerate(directions)]
    cutout.data = build_conversion_mesh(bpy.context, cutout)
    cutout.modifiers.clear()
    after = [render_normal(cutout, tmp_path / f"after-{i}.exr", d, with_uv_coverage=True) for i, d in enumerate(directions)]
    for direction, (original, source_coverage), (static, target_coverage) in zip(directions, before, after):
        np.testing.assert_array_equal(source_coverage, target_coverage)
        assert np.isfinite(static[source_coverage >= 0]).all()
        if direction == directions[-1]:
            assert np.count_nonzero(source_coverage == 0) > 0
        visible = source_coverage == 1
        from scipy.ndimage import binary_erosion
        visible = binary_erosion(visible, iterations=2)
        differences = np.linalg.norm(original[visible, :3] - static[visible, :3], axis=-1)
        assert len(differences) > 20
        assert np.quantile(differences, .95) < .04, (object_space, direction, original[32, 32], static[32, 32], np.quantile(differences, [.5, .95, 1]))


@pytest.mark.parametrize("thickness", [0, .15])
def test_depth_symmetry_materializes_regions_and_normals(symmetry, tmp_path, thickness):
    obj, _, _, set_cutout, set_mirror = symmetry
    obj["o_image_object"] = True
    build_image_layer_group()
    set_cutout("Mode", 1)
    set_cutout("Thickness", thickness, subtype="DISTANCE")
    set_cutout("Depth Scale", .5)
    set_mirror("Direction", (.15, .05, 1))
    set_mirror("Smooth", 2)
    color = bpy.data.images.new("Color", width=128, height=128, float_buffer=True)
    color.pixels.foreach_set(np.tile(np.array([.8, .3, .2, 1], dtype=np.float32), 128 * 128))
    normal = bpy.data.images.new("Normal", width=128, height=128, float_buffer=True)
    normal.colorspace_settings.name = "Non-Color"
    normal.pixels.foreach_set(np.tile(np.array([.65, .4, .95, 1], dtype=np.float32), 128 * 128))
    obj.data.materials.append(create_image_material(color, color, normal_image=normal, normal_space="OBJECT"))
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    directions = ((1, 0, 0), (-1, 0, 0))
    before = [render_normal(obj, tmp_path / f"s-before-{i}.exr", d) for i, d in enumerate(directions)]
    result = build_conversion_mesh(bpy.context, obj)
    assert not set(result.attributes.keys()) & PROTOCOL_ATTRIBUTES
    normal_result = next(n.image for n in result.materials[0].node_tree.nodes
                         if n.type == "TEX_IMAGE" and n.image.colorspace_settings.name == "Non-Color")
    assert tuple(normal_result.size) == ((256, 256) if thickness else (256, 128))
    obj.data = result
    obj.modifiers.clear()
    for i, (direction, original) in enumerate(zip(directions, before)):
        static = render_normal(obj, tmp_path / f"s-after-{i}.exr", direction)
        from scipy.ndimage import binary_erosion
        visible = binary_erosion(original[..., :3].max(axis=-1) > .01, iterations=2)
        differences = np.linalg.norm(original[visible, :3] - static[visible, :3], axis=-1)
        assert len(differences)
        assert np.quantile(differences, .95) < .04, (thickness, direction, np.quantile(differences, [.5, .95, 1]))


@pytest.mark.parametrize("execution", ["EXEC_DEFAULT", "INVOKE_DEFAULT"])
def test_conversion_operator_undo_redo(cutout, execution):
    name, mesh_name = cutout.name, cutout.data.name
    other = cutout.copy()
    bpy.context.collection.objects.link(other)
    other_name = other.name
    material_name = cutout.active_material.name
    bpy.context.preferences.edit.use_global_undo = True
    bpy.utils.register_class(ConvertToMesh)
    try:
        bpy.ops.ed.undo_push(message="Before Convert to Mesh")
        assert bpy.ops.anyimage.convert_to_mesh(execution, True) == {"FINISHED"}
        assert len(bpy.data.objects[name].modifiers) == 0
        assert bpy.data.objects[other_name].data.name == mesh_name
        assert bpy.data.objects[other_name].active_material.name == material_name
        assert not ConvertToMesh.poll(bpy.context)
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert len(bpy.data.objects[name].modifiers) == 1
        assert bpy.data.objects[name].data.name == mesh_name
        assert bpy.ops.ed.redo() == {"FINISHED"}
        assert len(bpy.data.objects[name].modifiers) == 0
        assert not set(bpy.data.objects[name].data.attributes.keys()) & PROTOCOL_ATTRIBUTES
    finally:
        bpy.utils.unregister_class(ConvertToMesh)


@pytest.mark.parametrize("float_color", [False, True])
def test_packed_static_images_survive_library_reload(cutout, tmp_path, float_color):
    from anyimage.common.image import image_pixels

    if not float_color:
        color = bpy.data.images.new("Byte Color", width=13, height=9, alpha=True)
        color.colorspace_settings.name = "sRGB"
        color.pixels.foreach_set(np.linspace(0, 1, 13 * 9 * 4, dtype=np.float32))
        next(n for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE").image = color
    cutout.data = build_conversion_mesh(bpy.context, cutout)
    cutout.modifiers.clear()
    images = [n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE"]
    expected = {i.name: (image_pixels(i), i.colorspace_settings.name, i.alpha_mode, i.is_float) for i in images}
    library = tmp_path / "static.blend"
    bpy.data.libraries.write(str(library), {cutout})
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(library)) as (available, loaded):
        loaded.objects = available.objects
    obj = loaded.objects[0]
    assert not set(obj.data.attributes.keys()) & PROTOCOL_ATTRIBUTES
    for node in obj.active_material.node_tree.nodes:
        if node.type != "TEX_IMAGE":
            continue
        image = node.image
        pixels, space, alpha, is_float = expected[image.name]
        assert image.packed_file and image.is_float == is_float
        assert image.colorspace_settings.name == space and image.alpha_mode == alpha
        np.testing.assert_array_equal(image_pixels(image), pixels)


def test_single_region_without_normal_preserves_user_attributes(cutout):
    modifier = cutout.modifiers[0]
    set_modifier_input(modifier, modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE"), 0)
    cutout.data.attributes.new("o_user_data", "FLOAT", "POINT")
    extra = cutout.data.uv_layers.new(name="UserUV")
    extra.data.foreach_set("uv", np.full(len(cutout.data.loops) * 2, .25, dtype=np.float32))
    nodes = cutout.active_material.node_tree.nodes
    layer = next(n for n in nodes if n.type == "GROUP")
    layer.inputs["Normal Scale"].default_value = .37
    nodes.remove(layer.inputs["Normal"].links[0].from_node)
    cutout.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    result = build_conversion_mesh(bpy.context, cutout)
    assert "o_user_data" in result.attributes
    assert "UserUV" in result.uv_layers
    assert all(tuple(item.uv) == (.25, .25) for item in result.uv_layers["UserUV"].data)
    images = [n.image for n in result.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"]
    assert len(images) == 1 and tuple(images[0].size) == (64, 64)
    static_layer = next(n for n in result.materials[0].node_tree.nodes if n.type == "GROUP")
    assert static_layer.inputs["Normal Scale"].default_value == 1


def test_bake_failure_keeps_source_and_cleans_resources(cutout, monkeypatch):
    from anyimage.operators.convert_to_mesh import materialization

    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))
    source = cutout.data
    def fail(*args, **kwargs):
        raise RuntimeError("Injected bake failure")
    monkeypatch.setattr(materialization, "bake_normal", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        build_conversion_mesh(bpy.context, cutout)
    assert cutout.data == source and len(cutout.modifiers) == 1
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes, bpy.data.node_groups))


def test_conversion_preserves_fixed_light_appearance(cutout, tmp_path):
    before = render_normal(cutout, tmp_path / "lit-before.exr", (0, -1, 0), lighting=True)
    cutout.data = build_conversion_mesh(bpy.context, cutout)
    cutout.modifiers.clear()
    after = render_normal(cutout, tmp_path / "lit-after.exr", (0, -1, 0), lighting=True)
    from scipy.ndimage import binary_erosion
    visible = binary_erosion(before[..., :3].max(axis=-1) > .01, iterations=4)
    differences = np.linalg.norm(before[visible, :3] - after[visible, :3], axis=-1)
    assert len(differences)
    assert np.quantile(differences, .95) < .06, np.quantile(differences, [.5, .95, 1])


def test_color_tiles_preserve_hdr_alpha_and_transparent_rgb(cutout):
    from anyimage.operators.convert_to_mesh.textures import build_color_tiles
    from anyimage.common.image import image_pixels

    image = next(n.image for n in cutout.active_material.node_tree.nodes if n.type == "TEX_IMAGE")
    pixels = image_pixels(image).reshape(64, 64, 4)
    pixels[:, :32, 3] = 0
    pixels[:, 32:, 3] = .25
    pixels[..., 2] = -.5
    image.pixels.foreach_set(pixels.ravel())
    result = build_color_tiles(image, ((1, 3), (0, 2)))
    np.testing.assert_array_equal(result[:64, :64], pixels[:, ::-1])
    np.testing.assert_array_equal(result[:64, 64:], pixels)
    np.testing.assert_array_equal(result[64:, :64], pixels)
    np.testing.assert_array_equal(result[64:, 64:], pixels[:, ::-1])

@pytest.mark.parametrize("regions,expected_tiles,offsets", [
    ((0,), ((0,),), ((0, 0),)),
    ((1,), ((1,),), ((0, 0),)),
    ((0, 1), ((1,), (0,)), ((0, 1), (0, 0))),
    ((0, 2), ((0, 2),), ((0, 0), (1, 0))),
    ((0, 1, 2, 3), ((1, 3), (0, 2)), ((0, 1), (0, 0), (1, 1), (1, 0))),
    ((0, 1, 3), ((1, 3), (0, None)), ((0, 1), (0, 0), (1, 0))),
])
def test_layout_preserves_surface_axes_and_composes_uv_flips(regions, expected_tiles, offsets):
    from anyimage.operators.convert_to_mesh.materialization import build_layout, SOURCE_UV, TARGET_UV
    mesh = bpy.data.meshes.new("Layout")
    try:
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)] * len(regions), [],
                        [(i * 3, i * 3 + 1, i * 3 + 2) for i in range(len(regions))])
        source = np.tile(np.array([[.1, .2], [.9, .3], [.4, .8]], dtype=np.float32), (len(regions), 1))
        mesh.uv_layers.new(name="UVMap").data.foreach_set("uv", source.ravel())
        mesh.attributes.new("o_image_region", "INT", "FACE").data.foreach_set("value", regions)
        tiles = build_layout(mesh)
        assert tiles == expected_tiles
        columns, rows = len(tiles[0]), len(tiles)
        actual = np.array([v.uv[:] for v in mesh.uv_layers[TARGET_UV].data])
        np.testing.assert_array_equal(np.array([v.uv[:] for v in mesh.uv_layers[SOURCE_UV].data]), source)
        for i in range(len(regions)):
            local = source[i * 3:i * 3 + 3].copy()
            if regions[i] in (1, 2):
                local[:, 0] = 1 - local[:, 0]
            expected = (local + offsets[i]) / (columns, rows)
            np.testing.assert_allclose(actual[i * 3:i * 3 + 3], expected)
    finally:
        bpy.data.meshes.remove(mesh)


def test_operator_is_blocking_and_reports_failure(cutout, monkeypatch):
    from anyimage.operators.convert_to_mesh import operators
    source = cutout.data
    monkeypatch.setattr(operators, "build_conversion_mesh", Mock(side_effect=RuntimeError("Bake failed")))
    operator = SimpleNamespace(report=Mock())
    assert ConvertToMesh.execute(operator, bpy.context) == {"CANCELLED"}
    operator.report.assert_called_once_with({"ERROR"}, "Bake failed")
    assert cutout.data == source and len(cutout.modifiers) == 1
    assert not {"invoke", "modal", "cancel", "_timer"} & ConvertToMesh.__dict__.keys()


def test_bake_context_setup_failure_releases_scene_and_object(cutout):
    from anyimage.operators.convert_to_mesh.materialization import bake_context

    scene = bpy.context.window.scene
    counts = (len(bpy.data.scenes), len(bpy.data.objects))
    with pytest.raises(ValueError, match="sequence expected"):
        with bake_context(cutout.data, cutout.active_material, object()):
            pytest.fail("Invalid matrix must fail during setup")
    assert bpy.context.window.scene == scene
    assert counts == (len(bpy.data.scenes), len(bpy.data.objects))


@pytest.mark.parametrize("stage", ["allocation", "bake"])
def test_normal_bake_failure_cleans_internal_resources(cutout, monkeypatch, stage):
    from anyimage.operators.convert_to_mesh import materialization

    material = cutout.active_material.copy()
    layer = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    group = layer.node_tree
    counts = (len(bpy.data.images), len(bpy.data.node_groups), len(material.node_tree.nodes))
    fail = Mock(side_effect=RuntimeError("Injected internal failure"))
    proxy = SimpleNamespace(data=bpy.data, context=bpy.context, ops=bpy.ops)
    if stage == "allocation":
        proxy.data = SimpleNamespace(images=SimpleNamespace(new=fail), node_groups=bpy.data.node_groups)
    else:
        proxy.ops = SimpleNamespace(object=SimpleNamespace(bake=fail))
    monkeypatch.setattr(materialization, "bpy", proxy)
    try:
        with pytest.raises(RuntimeError, match="Injected internal"):
            materialization.bake_normal(material, layer.name, (64, 128))
        assert layer.node_tree == group
        assert counts == (len(bpy.data.images), len(bpy.data.node_groups), len(material.node_tree.nodes))
    finally:
        bpy.data.materials.remove(material)


@pytest.mark.parametrize("invalid_input", ["modifier", "linked_strength", "reserved_uv", "missing_uv"])
def test_unsupported_input_preserves_source_and_releases_resources(cutout, monkeypatch, invalid_input):
    from anyimage.operators.convert_to_mesh import materialization

    if invalid_input == "modifier":
        cutout.modifiers.new("User bevel", "BEVEL")
    elif invalid_input == "linked_strength":
        tree = cutout.active_material.node_tree
        layer = next(n for n in tree.nodes if n.type == "GROUP")
        tree.links.new(tree.nodes.new("ShaderNodeValue").outputs[0], layer.inputs["Normal Scale"])
    elif invalid_input == "reserved_uv":
        cutout.data.uv_layers.new(name=materialization.SOURCE_UV)
    else:
        cutout.data.uv_layers.remove(cutout.data.uv_layers["UVMap"])
    cutout.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    source = cutout.data
    material = cutout.active_material
    modifiers = list(cutout.modifiers)
    counts = tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))
    bake = Mock(side_effect=AssertionError("Unsupported input must not reach baking"))
    monkeypatch.setattr(materialization, "bake_normal", bake)
    with pytest.raises(ValueError):
        build_conversion_mesh(bpy.context, cutout)
    bake.assert_not_called()
    assert cutout.data == source and cutout.active_material == material
    assert list(cutout.modifiers) == modifiers
    assert counts == tuple(len(items) for items in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.scenes))
