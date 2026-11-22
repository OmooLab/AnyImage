"""Create Blender data for a Cutout Shape."""

import bpy

from ...common.color_image import material_color_image
from ...common.geometry_image import camera_depth_values
from ...common.depth_geometry import (
    depth_limit_preset,
    depth_node_direction,
    depth_uniform_scale,
    fit_symmetry_depth_direction,
    reference_and_median_depth,
)
from ...common.image_plane import build_image_plane_matrix
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import (
    finalize_object_result,
    set_modifier_input,
)
from .geometry import (
    build_reference_mask,
    crop_plane_bounds,
    build_cutout_shape,
    CUTOUT_ALPHA_THRESHOLD,
)
from .shape import BALLOON_ATTRIBUTE_NAME, CUTOUT_NODE_GROUP_NAMES, DEPTH_CUTOUT_SHAPES
from .boundary_padding import pad_cutout_images
from ...preferences import DEFAULT_CUTOUT_BOUNDARY_PADDING


def create_cutout_mesh_object(context, source_object, bounds, base_shape, material):
    import numpy as np

    source_name = source_object.name
    mesh = bpy.data.meshes.new(source_name)
    mesh_object = None
    try:
        mesh.from_pydata(np.asarray(base_shape.vertices).tolist(), [], base_shape.faces)
        for face in mesh.polygons:
            face.use_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vertices)
        loop_uv = np.asarray(base_shape.uv, dtype=np.float32)[loop_vertices]
        uv_layer.data.foreach_set("uv", loop_uv.ravel())
        balloon = mesh.attributes.new(name=BALLOON_ATTRIBUTE_NAME, type="FLOAT", domain="POINT")
        balloon.data.foreach_set("value", np.asarray(base_shape.balloon, dtype=np.float32))
        mesh.materials.append(material)
        mesh.update()
        mesh_object = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(mesh_object)
        mesh_object.matrix_world = build_image_plane_matrix(source_object.matrix_world, bounds)
        mesh_object["o_image_object"] = True
        return mesh_object
    except Exception:
        if mesh_object is not None:
            bpy.data.objects.remove(mesh_object, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


def create_cutout_modifier(obj, group, shape, gesture):
    modifier = obj.modifiers.new(name=group.name, type="NODES")
    modifier.node_group = group
    modifier.show_group_selector = False
    set_modifier_input(
        modifier, "Thickness", 0.0 if shape == "FLAT" else 1.0,
        subtype="NONE" if shape in DEPTH_CUTOUT_SHAPES else None,
    )
    if gesture == "POLYLINE":
        set_modifier_input(modifier, "Mode", 1)
        if shape == "SOLID":
            set_modifier_input(modifier, "Thickness", 0.5, subtype="DISTANCE")
    return modifier


def create_shape_object(
    context,
    source_object,
    shape,
    bounds,
    base_shape,
    *,
    depth_pixels=None,
    content_values=None,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    depth_image=None,
    intrinsics=None,
    normal_image=None,
    color_image,
    gesture="LASSO",
):
    from mathutils import Matrix

    material = None
    mesh = None
    mesh_object = None
    try:
        material = create_image_material(
            source_object.data,
            color_image,
            normal_image=normal_image,
            normal_space="OBJECT",
            scene=context.scene,
        )
        mesh_object = create_cutout_mesh_object(
            context, source_object, bounds, base_shape, material
        )
        mesh = mesh_object.data
        node_group = load_node_group(
            CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID" if shape == "DEPTH_SYMMETRY" else shape]
        )
        modifier = create_cutout_modifier(mesh_object, node_group, shape, gesture)

        if shape in DEPTH_CUTOUT_SHAPES:
            if depth_image is None or intrinsics is None:
                raise ValueError("Depth Shape requires a Depth texture and camera intrinsics")
            reference_mask = build_reference_mask(content_values, depth_image.size, alpha_threshold)
            depth, valid = camera_depth_values(depth_pixels)
            model_reference, model_median = reference_and_median_depth(depth[valid & reference_mask])
            uniform_scale = depth_uniform_scale(bounds, depth_image.size, intrinsics, model_reference)
            depth_limit = depth_limit_preset(model_median, model_reference, uniform_scale)
            set_modifier_input(modifier, "Depth Scale", 1.0)
            set_modifier_input(modifier, "Uniform Scale", uniform_scale)
            set_modifier_input(modifier, "Reference Depth", model_reference * uniform_scale)
            set_modifier_input(modifier, "Depth Limit", depth_limit)
            set_modifier_input(modifier, "Depth Image", depth_image)

            if shape == "DEPTH_SYMMETRY":
                direction = fit_symmetry_depth_direction(
                    depth, valid, base_shape.vertices, base_shape.uv, uniform_scale,
                )
                mesh_object.matrix_world = mesh_object.matrix_world @ Matrix.Rotation(
                    -1.5707963267948966, 4, "Z"
                )
                set_modifier_input(modifier, "Front Inflation", 0.0)
                symmetry_group = load_node_group(CUTOUT_NODE_GROUP_NAMES[shape])
                symmetry = mesh_object.modifiers.new(name=symmetry_group.name, type="NODES")
                symmetry.node_group = symmetry_group
                symmetry.show_group_selector = False
                set_modifier_input(symmetry, "Direction", depth_node_direction(direction))
        return finalize_object_result(
            context,
            source_object,
            mesh_object,
            keep_source=True,
        )
    except Exception:
        if mesh_object is not None:
            bpy.data.objects.remove(mesh_object, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material)
        raise


def push_cutout_undo(shape):
    message = f"Convert to {shape.replace('_', ' ').title()}"
    if "FINISHED" not in bpy.ops.ed.undo_push(message=message):
        raise RuntimeError(f"Unable to create the {message} Undo step")


def create_cutout_shape(
    context,
    source_object,
    shape,
    edge_length,
    selection,
    *,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    fine_outline=False,
    depth_image=None,
    intrinsics=None,
    normal_image=None,
    boundary_padding=DEFAULT_CUTOUT_BOUNDARY_PADDING,
    source_rgba,
    gesture="LASSO",
    report=None,
):
    bounds = crop_plane_bounds(source_object, selection.bounds, source_object.data.size)
    base_shape = build_cutout_shape(
        context, source_object, edge_length, selection.values, bounds,
        alpha_threshold, fine_outline, report,
    )
    left, top, right, bottom = selection.bounds
    depth_pixels = pad_cutout_images(
        source_rgba[top:bottom, left:right],
        depth_image,
        intrinsics,
        base_shape.mask,
        boundary_padding,
    )
    with material_color_image(source_object.data, bounds=selection.bounds, rgba=source_rgba) as color_image:
        result = create_shape_object(
            context,
            source_object,
            shape,
            bounds,
            base_shape,
            content_values=selection.values,
            depth_pixels=depth_pixels,
            alpha_threshold=alpha_threshold,
            depth_image=depth_image,
            intrinsics=intrinsics,
            normal_image=normal_image,
            color_image=color_image,
            gesture=gesture,
        )
    push_cutout_undo(shape)
    return result
