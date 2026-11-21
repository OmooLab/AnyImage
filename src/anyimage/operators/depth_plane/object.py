"""Load geometry artifacts and create depth-based plane objects."""

import bpy

from ...common.image import image_empty_bounds, image_rgba
from ...common.depth_geometry import (
    depth_plane_limit_preset,
    depth_node_direction,
    depth_uniform_scale,
    fit_image_depth_direction,
    reference_and_median_depth,
)
from ...common.geometry_image import (
    camera_depth_values,
    load_depth_metadata,
    load_depth_result_image,
    load_normal_result_image,
)
from ...common.material import create_image_material
from ...common.color_image import material_color_image
from ...common.object import (
    finalize_object_result,
    modifier_input_identifier,
    read_conversion_source,
    set_modifier_input,
)
from ...common.node import load_node_group
from ...common.image_plane import (
    build_image_plane_matrix,
    create_image_plane_mesh,
)


def create_depth_plane_object(
    context,
    source_object,
    subdivisions,
    material,
    depth_image,
    depth_metadata,
    plane_type,
):
    node_group = load_node_group({
        "DEPTH": "O Depth Plane",
        "RELIEF": "O Depth Relief",
    }[plane_type])
    source_name = source_object.name
    bounds = image_empty_bounds(source_object)
    mesh = create_image_plane_mesh(source_name, bounds)
    plane = None
    try:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        mesh.materials.append(material)
        plane = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(plane)
        plane.matrix_world = build_image_plane_matrix(source_object.matrix_world, bounds)
        plane["o_image_object"] = True

        modifier = plane.modifiers.new(name=node_group.name, type="NODES")
        modifier.node_group = node_group
        modifier.show_group_selector = False
        depth, valid = camera_depth_values(depth_image)
        values = depth[valid]
        model_reference, model_median = reference_and_median_depth(values)
        uniform_scale = depth_uniform_scale(bounds, depth_metadata, model_reference)
        inputs = [
            ("Subdivide", max(0, min(8, int(subdivisions)))),
            ("Reference Depth", model_reference * uniform_scale),
            ("Uniform Scale", uniform_scale),
            ("Depth Image", depth_image),
        ]
        if plane_type == "DEPTH":
            limit = depth_plane_limit_preset(values, model_median, model_reference, uniform_scale)
            inputs.append(("Depth Limit", limit))
        else:
            depth_direction = depth_node_direction(
                fit_image_depth_direction(depth, valid, bounds, uniform_scale)
            )
            inputs.append((
                "Depth Direction",
                depth_direction,
            ))
        for name, value in inputs:
            set_modifier_input(
                modifier,
                modifier_input_identifier(node_group, name),
                value,
            )
        return finalize_object_result(context, source_object, plane)
    except Exception:
        if plane is not None:
            bpy.data.objects.remove(plane, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


def create_depth_plane_from_result(context, result, operator, *, plane_type, undo_label):
    normal_space = {"DEPTH": "OBJECT", "RELIEF": "TANGENT"}[plane_type]
    source_object, pixels = read_conversion_source(operator)
    material = None
    depth_image = None
    normal_image = None
    try:
        with material_color_image(source_object.data, rgba=image_rgba(source_object.data, pixels)) as color_image:
            depth_metadata = load_depth_metadata(result.file("depth_metadata"))
            depth_image = load_depth_result_image(
                result.file("depth"), source_object, depth_metadata,
            )
            normal_image = load_normal_result_image(
                result.file(f"{normal_space.lower()}_normal"), source_object,
            )
            material = create_image_material(
                source_object.data, color_image,
                color_is_full_source=True,
                normal_image=normal_image, normal_space=normal_space,
                scene=context.scene,
            )
            create_depth_plane_object(
                context, source_object, 6, material,
                depth_image, depth_metadata, plane_type,
            )
    except Exception:
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)
        for image in (depth_image, normal_image):
            if image is not None and image.users == 0:
                bpy.data.images.remove(image, do_unlink=True)
        raise
    if "FINISHED" not in bpy.ops.ed.undo_push(message=undo_label):
        raise RuntimeError(f"Unable to create the {undo_label} Undo step")
