"""Compare the single-attribute shader with independently transformed normals."""

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from anyimage.common.node import load_node_group
from tests.support.depth_symmetry import symmetry
from tests.support.materials import render_engine


def test_symmetry_normal_transform_matches_object_normals(symmetry, render_engine, tmp_path):
    obj, _, mirror, _, set_mirror = symmetry
    group = load_node_group("O Texture to Layer")
    source_normal = Vector((.3, -.8, .5)).normalized()
    samples = []
    for direction, scale in [((0, 0, 1), 1), ((.35, .2, 1), .4),
                             ((-.2, .3, 1), 1.7), ((0, 0, -1), 1)]:
        set_mirror("Direction", direction)
        set_mirror("Scale", scale)
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
        transforms = np.array([item.vector[:] for item in mesh.attributes["o_normal_transform"].data])
        assert len(transforms)
        target = Vector((direction[0], direction[2], direction[1])).normalized()
        rotation = (Quaternion((0, 0, 1), np.pi) if target.y < -1 + 1e-6
                    else Vector((0, 1, 0)).rotation_difference(target))
        for sign in (1, -1):
            value = transforms[transforms[:, 2] * sign > 0][0]
            normal = rotation.inverted() @ source_normal
            normal.y *= sign / scale
            expected = Matrix.Rotation(np.pi / 2, 3, "Z") @ normal.normalized()
            samples.append((value, expected))

    # Inspect the producer before face deletion to exercise Scale=0, where the
    # final mesh may be empty. The actual geometry still uses the user's zero.
    probe = mirror.node_group.copy()
    mirror.node_group = probe
    output = next(n for n in probe.nodes if n.type == "GROUP_OUTPUT")
    store = next(n for n in probe.nodes if n.type == "STORE_NAMED_ATTRIBUTE"
                 and n.inputs["Name"].default_value == "o_normal_transform"
                 and n.inputs["Geometry"].links[0].from_node.type == "SET_POSITION")
    probe.links.new(store.outputs["Geometry"], output.inputs["Geometry"])
    set_mirror("Direction", (0, 0, 1))
    set_mirror("Scale", 0)
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    value = np.array(mesh.attributes["o_normal_transform"].data[0].vector[:])
    assert np.isfinite(value).all() and value[2] == 1e6
    np.testing.assert_allclose([v.co.y for v in mesh.vertices], 0)
    samples.append((value, Vector((1, 0, 0))))
    samples.append((None, source_normal))
    obj.hide_render = True

    for column, (value, expected) in enumerate(samples):
        for reference in (False, True):
            bpy.ops.mesh.primitive_plane_add(size=.8, location=(column, .5 if reference else -.5, 0))
            plane = bpy.context.object
            if value is not None and not reference:
                attribute = plane.data.attributes.new("o_normal_transform", "FLOAT_VECTOR", "FACE")
                attribute.data[0].vector = value
            material = bpy.data.materials.new("Reference" if reference else "Transformed")
            material.use_nodes = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            nodes.clear()
            normal = nodes.new("ShaderNodeNormalMap" if reference else "ShaderNodeGroup")
            if reference:
                normal.space = "OBJECT"
                normal.inputs["Color"].default_value = (*((np.array(expected) + 1) / 2), 1)
            else:
                normal.node_tree = group
                normal.inputs["Normal Texture"].default_value = (*((np.array(source_normal) + 1) / 2), 1)
                normal.inputs["Object Space"].default_value = True
                normal.inputs["Bump Scale"].default_value = 0
            encode = nodes.new("ShaderNodeVectorMath")
            encode.operation = "MULTIPLY_ADD"
            encode.inputs[1].default_value = (.5, .5, .5)
            encode.inputs[2].default_value = (.5, .5, .5)
            links.new(normal.outputs["Normal"], encode.inputs[0])
            emission = nodes.new("ShaderNodeEmission")
            output = nodes.new("ShaderNodeOutputMaterial")
            links.new(encode.outputs[0], emission.inputs["Color"])
            links.new(emission.outputs[0], output.inputs["Surface"])
            plane.data.materials.append(material)

    scene = bpy.context.scene
    scene.render.engine = render_engine
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = len(samples) * 32, 64
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.filepath = str(tmp_path / "normal_transform.exr")
    bpy.ops.object.camera_add(location=((len(samples) - 1) / 2, 0, 5))
    scene.camera = bpy.context.object
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = len(samples)
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
    try:
        pixels = np.array(rendered.pixels[:]).reshape(64, len(samples) * 32, 4)
        columns = np.arange(len(samples)) * 32 + 16
        assert np.isfinite(pixels).all()
        np.testing.assert_allclose(pixels[16, columns, :3], pixels[48, columns, :3], atol=1e-3)
    finally:
        bpy.data.images.remove(rendered)
        bpy.ops.wm.read_factory_settings(use_empty=True)
