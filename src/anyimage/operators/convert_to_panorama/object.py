"""Apply packed panorama artifacts around the source Empty's camera origin."""

import json
from pathlib import Path

import bpy

from ...common.color_image import material_color_image
from ...common.geometry_image import load_depth_result_image, normal_data_name
from ...common.image_target import require_conversion_source
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import finalize_object_result, modifier_input_identifier, set_modifier_input
from .normal import bake_panorama_normal
from .world import create_panorama_world


def load_panorama_metadata(path):
    metadata = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        size = tuple(int(value) for value in metadata["image_size"])
        valid = (metadata["projection"] == "equirectangular" and len(size) == 2
                 and size[1] > 0 and size[0] == 2 * size[1])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Panorama metadata is invalid") from error
    if not valid:
        raise ValueError("Panorama metadata is invalid")
    return {"image_size": size}


def create_panorama_from_result(context, result, operator):
    source = require_conversion_source(operator)
    depth = relief = normal = material = mesh = obj = world = None
    previous_world = context.scene.world
    try:
        with material_color_image(input_path=operator.color_path) as color:
            metadata = load_panorama_metadata(result.file("depth_metadata"))
            group = load_node_group("O Depth Panorama")
            depth = load_depth_result_image(result.file("depth"), source, metadata)
            relief = bpy.data.images.load(str(result.file("object_normal")), check_existing=False)
            relief.colorspace_settings.is_data = True
            material = create_image_material(
                source.data, color,
                normal_image=relief, normal_space="OBJECT",
                scene=context.scene, texture_extension="REPEAT", emission_strength=1.0, panorama=True)
            material.use_backface_culling = True
            material.use_backface_culling_shadow = True
            mesh = bpy.data.meshes.new(source.name)
            mesh.from_pydata([(0, 0, 0)], [], [])
            mesh.materials.append(material)
            obj = bpy.data.objects.new(source.name, mesh)
            context.collection.objects.link(obj)
            obj.location = source.matrix_world.translation
            obj.scale = source.matrix_world.to_scale()
            obj.visible_shadow = False
            obj["o_image_object"] = True
            modifier = obj.modifiers.new(group.name, "NODES")
            modifier.node_group = group
            modifier.show_group_selector = False
            for name, value in (
                ("Subdivide", 6), ("Depth Image", depth),
                ("Depth Mask", True), ("Depth Split", 0.01),
            ):
                set_modifier_input(modifier, modifier_input_identifier(group, name), value)
            horizon_bend = modifier_input_identifier(group, "Horizon Bend")
            set_modifier_input(modifier, horizon_bend, 0.0)
            obj.update_tag(refresh={"DATA"})
            normal = bake_panorama_normal(context, obj, depth, result.file("normal_coverage"),
                                          name=normal_data_name(source))
            bpy.data.images.remove(relief)
            relief = None
            set_modifier_input(modifier, horizon_bend, -0.1)
            obj.update_tag(refresh={"DATA"})
            world = create_panorama_world(obj, source.data, color)
            context.scene.world = world
            finalize_object_result(context, source, obj)
    except Exception:
        if world is not None:
            context.scene.world = previous_world
            bpy.data.worlds.remove(world, do_unlink=True)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)
        for image in (depth, relief, normal):
            if image is not None and image.users == 0:
                bpy.data.images.remove(image, do_unlink=True)
        raise
    if "FINISHED" not in bpy.ops.ed.undo_push(message="Convert to Panorama"):
        raise RuntimeError("Unable to create the Convert to Panorama Undo step")
    return obj
