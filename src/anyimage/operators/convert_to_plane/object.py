"""Create Blender Image, Material, Mesh, and Object data for Plane conversion."""

import bpy

from ...common.image import (
    image_empty_bounds,
    load_normal_result_image,
    require_conversion_source,
)
from ...common.depth import (
    depth_uniform_scale,
    fit_image_depth_direction,
    load_depth_metadata,
    load_depth_result_image,
    reference_depth,
)
from ...common.coordinate import canonical_direction_to_legacy
from ...common.material import create_image_material
from ...common.color_image import material_color_image
from ...common.object import (
    finalize_object_result,
    modifier_input_identifier,
    set_modifier_input,
)
from ...common.node import load_node_group
from .image_plane import (
    build_image_plane_matrix,
    create_image_plane_mesh,
    create_image_plane_object,
)


def create_plane_object(context, source_object, subdivisions, material):
    source_name = source_object.name
    plane = create_image_plane_object(
        context,
        source_name,
        image_empty_bounds(source_object),
        material,
        matrix_world=source_object.matrix_world,
        subdivisions=subdivisions,
    )
    try:
        for polygon in plane.data.polygons:
            polygon.use_smooth = True
        plane["anyimage_mesh_shape"] = "PLANE"
        return finalize_object_result(context, source_object, plane)
    except Exception:
        mesh = plane.data
        bpy.data.objects.remove(plane, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


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
        "DEPTH": "O Image Depth Plane",
        "RELIEF": "O Image Relief Plane",
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
        plane["anyimage_mesh_shape"] = f"{plane_type}_PLANE"

        modifier = plane.modifiers.new(name=node_group.name, type="NODES")
        modifier.node_group = node_group
        modifier.show_group_selector = False
        model_reference = reference_depth(depth_image)
        uniform_scale = depth_uniform_scale(
            source_object,
            depth_metadata,
            model_reference,
        )
        inputs = [
            ("Subdivide", max(0, min(10, int(subdivisions)))),
            ("Reference Depth", model_reference * uniform_scale),
            ("Uniform Scale", uniform_scale),
            ("Depth Image", depth_image),
        ]
        if plane_type == "RELIEF":
            depth_direction = canonical_direction_to_legacy(
                fit_image_depth_direction(
                    depth_image,
                    bounds,
                    uniform_scale,
                )
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


def create_depth_plane_from_result(context, result, operator):
    normal_space = {"DEPTH": "OBJECT", "RELIEF": "TANGENT"}[operator.plane_type]
    source_object = require_conversion_source(operator)
    material = None
    depth_image = None
    normal_image = None
    try:
        with material_color_image(input_path=operator.color_path) as color_image:
            depth_metadata = load_depth_metadata(result.file("depth_metadata"))
            depth_image = load_depth_result_image(
                result.file("depth"), source_object, depth_metadata,
            )
            normal_image = load_normal_result_image(
                result.file(f"{normal_space.lower()}_normal"), source_object,
            )
            material = create_image_material(
                source_object.data, color_image,
                normal_image=normal_image, normal_space=normal_space,
                scene=context.scene,
            )
            create_depth_plane_object(
                context, source_object, operator.mesh_detail, material,
                depth_image, depth_metadata, operator.plane_type,
            )
    except Exception:
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material, do_unlink=True)
        for image in (depth_image, normal_image):
            if image is not None and image.users == 0:
                bpy.data.images.remove(image, do_unlink=True)
        raise
    label = f"Convert to {operator.plane_type.title()} Plane"
    if "FINISHED" not in bpy.ops.ed.undo_push(message=label):
        raise RuntimeError(f"Unable to create the {label} Undo step")
