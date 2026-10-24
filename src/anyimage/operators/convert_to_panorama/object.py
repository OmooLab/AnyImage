"""Apply packed panorama artifacts around the source Empty's camera origin."""

import json
from pathlib import Path

import bpy

from ...common.geometry_image import load_depth_result_image, load_normal_result_image
from ...common.image import require_conversion_source
from ...common.color_image import material_color_image
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import finalize_object_result, modifier_input_identifier, set_modifier_input
from ...ai_preferences import configured_panorama_light_probe
from .light_probe import create_panorama_light_probe, bake_panorama_light_probe


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
    depth = normal = material = mesh = obj = probe = None
    try:
        with material_color_image(input_path=operator.color_path) as color:
            metadata = load_panorama_metadata(result.file("depth_metadata"))
            group = load_node_group("O Image Depth Panorama")
            depth = load_depth_result_image(result.file("depth"), source, metadata)
            normal = load_normal_result_image(result.file("object_normal"), source)
            if tuple(normal.size) != metadata["image_size"]:
                raise ValueError("Normal texture dimensions do not match panorama metadata")
            material = create_image_material(
                source.data, color, normal_image=normal, normal_space="OBJECT",
                scene=context.scene, texture_extension="REPEAT", emission_strength=1.0)
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
                ("Subdivide", 8), ("Depth Image", depth),
            ):
                set_modifier_input(modifier, modifier_input_identifier(group, name), value)
            obj.update_tag(refresh={"DATA"})
            enabled, max_distance = configured_panorama_light_probe(context)
            if enabled:
                context.view_layer.update()
                probe = create_panorama_light_probe(context, obj, max_distance)
                if probe is None:
                    operator.report({"WARNING"}, "Panorama has no valid light probe region")
                else:
                    probe.name = f"{source.name}_LightProbe"
                    probe.data.name = probe.name
                    bake_panorama_light_probe(context, obj, probe)
                    probe.hide_select = True
            finalize_object_result(context, source, obj)
    except Exception:
        if probe is not None:
            probe_data = probe.data
            bpy.data.objects.remove(probe, do_unlink=True)
            bpy.data.lightprobes.remove(probe_data)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)
        if normal is not None and normal.users == 0:
            bpy.data.images.remove(normal, do_unlink=True)
        if depth is not None and depth.users == 0:
            bpy.data.images.remove(depth, do_unlink=True)
        raise
    if "FINISHED" not in bpy.ops.ed.undo_push(message="Convert to Panorama"):
        raise RuntimeError("Unable to create the Convert to Panorama Undo step")
    return obj
