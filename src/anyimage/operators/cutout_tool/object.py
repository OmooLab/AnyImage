"""Create Blender data for a Cutout Shape."""

import bpy

from ...common.geometry_image import (
    DEPTH_LIMIT_MEDIAN_FACTOR,
    depth_node_direction,
    depth_uniform_scale,
    fit_symmetry_depth_direction,
    median_depth,
    reference_depth,
)
from ...common.material import create_image_material
from ...common.node import load_node_group
from ...common.object import (
    finalize_object_result,
    blender_frame_rotation,
    modifier_input_identifier,
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


def create_cutout_mesh_object(context, source_object, content_bounds, base_shape, material):
    import numpy as np
    from mathutils import Matrix

    bounds = crop_plane_bounds(source_object, content_bounds, tuple(source_object.data.size))
    crop_center = ((bounds[0] + bounds[1]) * 0.5, (bounds[2] + bounds[3]) * 0.5)
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
        mesh_object.matrix_world = (
            source_object.matrix_world
            @ Matrix.Translation((*crop_center, 0.0))
            @ blender_frame_rotation().inverted()
        )
        mesh_object["o_image_object"] = True
        return mesh_object
    except Exception:
        if mesh_object is not None:
            bpy.data.objects.remove(mesh_object, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise


def create_cutout_modifier(obj, group, shape, gesture, *, thickness_subtype=None):
    modifier = obj.modifiers.new(name=group.name, type="NODES")
    modifier.node_group = group
    modifier.show_group_selector = False
    set_modifier_input(
        modifier,
        modifier_input_identifier(group, "Thickness", subtype=thickness_subtype),
        0.0 if shape == "FLAT" else 1.0,
    )
    if gesture == "POLYLINE":
        set_modifier_input(modifier, modifier_input_identifier(group, "Mode"), 1)
        if shape == "SOLID":
            set_modifier_input(
                modifier, modifier_input_identifier(group, "Thickness", subtype="DISTANCE"), 0.5
            )
    return modifier


def create_shape_object(
    context,
    source_object,
    shape,
    content_bounds,
    base_shape,
    *,
    content_values=None,
    depth_image=None,
    depth_metadata=None,
    normal_image=None,
    normal_mode="NONE",
    color_image,
    gesture="LASSO",
):
    from mathutils import Matrix

    if shape in DEPTH_CUTOUT_SHAPES:
        normal_mode = "OBJECT"
    elif normal_mode not in {"NONE", "TANGENT", "OBJECT"}:
        raise ValueError(f"Unsupported Cutout normal mode: {normal_mode}")
    bounds = crop_plane_bounds(
        source_object,
        content_bounds,
        tuple(source_object.data.size),
    )
    material = None
    mesh = None
    mesh_object = None
    try:
        material = create_image_material(
            source_object.data,
            color_image,
            normal_image=normal_image,
            normal_space="TANGENT" if normal_mode == "NONE" else normal_mode,
            scene=context.scene,
        )
        depth_reference = None
        depth_limit = None
        uniform_scale = None
        depth_direction = None
        if shape in DEPTH_CUTOUT_SHAPES:
            if depth_image is None or depth_metadata is None:
                raise ValueError("Depth Shape requires a Depth texture and metadata")
            front_size = depth_metadata["image_size"]
            reference_mask = build_reference_mask(content_values, front_size)
            model_reference = reference_depth(depth_image, reference_mask)
            model_median = median_depth(depth_image, reference_mask)
            uniform_scale = depth_uniform_scale(
                source_object,
                depth_metadata,
                model_reference,
                bounds,
            )
            depth_reference = model_reference * uniform_scale
            depth_limit = max(
                (DEPTH_LIMIT_MEDIAN_FACTOR * model_median - model_reference) * uniform_scale,
                0.0,
            )
            if shape == "DEPTH_SYMMETRY":
                depth_direction = depth_node_direction(
                    fit_symmetry_depth_direction(
                        depth_image,
                        base_shape.vertices,
                        base_shape.uv,
                        uniform_scale,
                    )
                )

        mesh_object = create_cutout_mesh_object(
            context, source_object, content_bounds, base_shape, material
        )
        mesh = mesh_object.data
        if shape == "DEPTH_SYMMETRY":
            mesh_object.matrix_world = mesh_object.matrix_world @ Matrix.Rotation(
                -1.5707963267948966, 4, "Z"
            )
        node_group = load_node_group(
            CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID" if shape == "DEPTH_SYMMETRY" else shape]
        )
        modifier = create_cutout_modifier(
            mesh_object, node_group, shape, gesture,
            thickness_subtype="NONE" if shape in DEPTH_CUTOUT_SHAPES else None,
        )
        if shape in DEPTH_CUTOUT_SHAPES:
            for name, value in (
                ("Depth Scale", 1.0),
                ("Uniform Scale", uniform_scale),
                ("Reference Depth", depth_reference),
                ("Depth Limit", depth_limit),
                ("Depth Image", depth_image),
            ):
                set_modifier_input(
                    modifier,
                    modifier_input_identifier(node_group, name),
                    value,
                )
        if shape == "DEPTH_SYMMETRY":
            set_modifier_input(
                modifier,
                modifier_input_identifier(node_group, "Front Inflation"),
                0.0,
            )
            symmetry_group = load_node_group(CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"])
            symmetry = mesh_object.modifiers.new(name=symmetry_group.name, type="NODES")
            symmetry.node_group = symmetry_group
            symmetry.show_group_selector = False
            set_modifier_input(
                symmetry,
                modifier_input_identifier(symmetry_group, "Direction"),
                depth_direction,
            )
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
    content_values,
    content_bounds,
    *,
    alpha_threshold=CUTOUT_ALPHA_THRESHOLD,
    fine_outline=False,
    depth_image=None,
    depth_metadata=None,
    normal_image=None,
    normal_mode="NONE",
    boundary_padding=DEFAULT_CUTOUT_BOUNDARY_PADDING,
    color_image,
    gesture="LASSO",
    report=None,
):
    base_shape = build_cutout_shape(
        context, source_object, edge_length, content_values, content_bounds,
        alpha_threshold, fine_outline, report,
    )
    pad_cutout_images(
        color_image,
        depth_image,
        depth_metadata,
        base_shape.mask,
        0.5,
        boundary_padding,
    )
    result = create_shape_object(
        context,
        source_object,
        shape,
        content_bounds,
        base_shape,
        content_values=content_values,
        depth_image=depth_image,
        depth_metadata=depth_metadata,
        normal_image=normal_image,
        normal_mode=normal_mode,
        color_image=color_image,
        gesture=gesture,
    )
    push_cutout_undo(shape)
    return result
