"""Apply packed panorama artifacts around the source Empty's camera origin."""

import bpy

from ...common.color_image import material_color_image
from ...common.geometry_image import load_depth_result_image, normal_data_name
from ...common.image import image_rgba
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import (
    finalize_object_result,
    read_conversion_source,
    set_modifier_input,
)
from ...common.panorama import create_panorama_world
from .normal import bake_panorama_normal


def create_panorama_from_result(context, result, operator):
    source, pixels = read_conversion_source(operator)
    depth = normal = material = mesh = obj = world = None
    previous_world = context.scene.world
    try:
        depth = load_depth_result_image(result.file("depth"), source)
        depth.pack()
        width, height = depth.size
        if height <= 0 or width != 2 * height:
            raise ValueError("Panorama depth texture must have a 2:1 aspect ratio")
        with material_color_image(
            source.data, bounds=operator.crop_bounds, rgba=image_rgba(source.data, pixels),
        ) as color:
            group = load_node_group("O Depth Panorama")
            normal = bpy.data.images.load(str(result.file("object_normal")), check_existing=False)
            normal.name = normal_data_name(source)
            normal.colorspace_settings.is_data = True
            normal.alpha_mode = "CHANNEL_PACKED"
            material = create_image_material(
                source.data, color,
                color_is_full_source=tuple(color.size) == tuple(source.data.size),
                normal_image=normal, normal_space="OBJECT",
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
                set_modifier_input(modifier, name, value)
            set_modifier_input(modifier, "Horizon Bend", 0.0)
            obj.update_tag(refresh={"DATA"})
            bake_panorama_normal(context, obj, normal, depth)
            set_modifier_input(modifier, "Horizon Bend", -0.1)
            obj.update_tag(refresh={"DATA"})
            world = create_panorama_world(source.data, color, panorama_object=obj)
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
        for image in (depth, normal):
            if image is not None and image.users == 0:
                bpy.data.images.remove(image, do_unlink=True)
        raise
    if "FINISHED" not in bpy.ops.ed.undo_push(message="Convert to Panorama"):
        raise RuntimeError("Unable to create the Convert to Panorama Undo step")
    return obj
