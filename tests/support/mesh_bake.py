"""Compare material normals and visible UV coverage during mesh baking."""

import bpy
import numpy as np
from mathutils import Vector

from anyimage.common.object import set_modifier_input


def add_post_bake_modifiers(obj, depth_image=None):
    """Append a deformation, duplicated geometry and disabled modifiers."""
    deform = obj.modifiers.new("User displacement", "DISPLACE")
    deform.direction = "X"
    deform.mid_level = 0
    deform.strength = .3
    deform.keyframe_insert(data_path="strength", frame=1)
    deform.strength = .6
    deform.keyframe_insert(data_path="strength", frame=2)
    deform.driver_add("mid_level").driver.expression = "0"
    bpy.context.scene.frame_set(1)

    group = bpy.data.node_groups.new("User geometry", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    offset = group.interface.new_socket(name="Offset", in_out="INPUT", socket_type="NodeSocketVector")
    image = group.interface.new_socket(name="Depth Image", in_out="INPUT", socket_type="NodeSocketImage")
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    transform = group.nodes.new("GeometryNodeTransform")
    join = group.nodes.new("GeometryNodeJoinGeometry")
    group.links.new(source.outputs["Geometry"], transform.inputs["Geometry"])
    group.links.new(source.outputs["Offset"], transform.inputs["Translation"])
    group.links.new(source.outputs["Geometry"], join.inputs["Geometry"])
    group.links.new(transform.outputs["Geometry"], join.inputs["Geometry"])
    group.links.new(join.outputs["Geometry"], output.inputs["Geometry"])
    nodes = obj.modifiers.new("User nodes", "NODES")
    nodes.node_group = group
    nodes.show_render = False
    set_modifier_input(nodes, offset.identifier, (4, 0, 0))
    set_modifier_input(nodes, image.identifier, depth_image)
    disabled = obj.modifiers.new("Disabled bevel", "BEVEL")
    disabled.show_viewport = False
    empty = obj.modifiers.new("Empty nodes", "NODES")
    empty.show_viewport = empty.show_render = False
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    return deform, nodes, disabled, empty


def mesh_geometry(mesh):
    """Snapshot positions and face connectivity independently of mesh lifetime."""
    return np.array([v.co[:] for v in mesh.vertices]), [tuple(p.vertices) for p in mesh.polygons]


def modifier_inputs(modifier):
    """Copy Geometry Nodes inputs without retaining IDProperty array views."""
    return {name: value.to_list() if hasattr(value, "to_list") else value for name, value in modifier.items()}


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
