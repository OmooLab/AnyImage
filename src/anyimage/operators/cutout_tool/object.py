"""Create Blender data for a Cutout Shape."""

from enum import StrEnum

import bpy

from ...common.coordinate import canonical_direction_to_symmetry_legacy
from ...common.depth import (
    DEPTH_LIMIT_MEDIAN_FACTOR,
    depth_uniform_scale,
    fit_symmetry_depth_direction,
    median_depth,
    reference_depth,
)
from ...common.material import create_image_material
from ...common.object import (
    blender_frame_rotation,
    finalize_object_result,
    modifier_input_identifier,
    set_modifier_input,
)
from ...common.node import load_node_group
from .geometry import (
    build_reference_mask,
    crop_plane_bounds,
)
from .shape import (
    BALLOON_ATTRIBUTE_NAME,
    CUTOUT_NODE_GROUP_NAMES,
    DEPTH_CUTOUT_SHAPES,
)


class NormalMode(StrEnum):
    NONE = "NONE"
    TANGENT = "TANGENT"
    OBJECT = "OBJECT"


def _cutout_world_matrix(source_matrix, crop_center):
    from mathutils import Matrix

    center_x, center_y = (float(value) for value in crop_center)
    return (
        source_matrix
        @ Matrix.Translation((center_x, center_y, 0.0))
        @ blender_frame_rotation().inverted()
    )


def _assign_uv(mesh, uv):
    import numpy as np

    for layer in list(mesh.uv_layers):
        mesh.uv_layers.remove(layer)
    uv_layer = mesh.uv_layers.new(name="UVMap")
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    loop_uv = np.asarray(uv, dtype=np.float32)[loop_vertices]
    uv_layer.data.foreach_set("uv", loop_uv.ravel())


def _assign_float_point_attribute(mesh, name, values):
    import numpy as np

    attribute = mesh.attributes.new(name=name, type="FLOAT", domain="POINT")
    attribute.data.foreach_set("value", np.asarray(values, dtype=np.float32))




def load_cutout_node_group(shape):
    return load_node_group(CUTOUT_NODE_GROUP_NAMES[shape])


def create_shape_object(
    context,
    source_object,
    shape,
    content_values,
    content_bounds,
    base_shape,
    *,
    depth_image=None,
    depth_metadata=None,
    normal_image=None,
    normal_mode=NormalMode.NONE,
    color_image,
    gesture="LASSO",
):
    import numpy as np
    from mathutils import Matrix

    normal_mode = NormalMode.OBJECT if shape in DEPTH_CUTOUT_SHAPES else NormalMode(normal_mode)
    bounds = crop_plane_bounds(
        source_object,
        content_bounds,
        tuple(source_object.data.size),
    )
    crop_center = (
        (bounds[0] + bounds[1]) * 0.5,
        (bounds[2] + bounds[3]) * 0.5,
    )
    material = None
    mesh = None
    mesh_object = None
    try:
        material = create_image_material(
            source_object.data,
            color_image,
            normal_image=normal_image,
            normal_space=(
                NormalMode.TANGENT.value
                if normal_mode == NormalMode.NONE
                else normal_mode.value
            ),
            scene=context.scene,
        )
        depth_reference = None
        depth_limit = None
        uniform_scale = None
        depth_direction = None
        if shape in DEPTH_CUTOUT_SHAPES:
            if depth_image is None or depth_metadata is None:
                raise ValueError("Depth Shape requires a Depth texture and metadata")
            reference_mask = build_reference_mask(content_values, depth_image.size)
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
                (DEPTH_LIMIT_MEDIAN_FACTOR * model_median - model_reference)
                * uniform_scale,
                0.0,
            )
            if shape == "DEPTH_SYMMETRY":
                depth_direction = canonical_direction_to_symmetry_legacy(
                    fit_symmetry_depth_direction(
                        depth_image,
                        base_shape.vertices,
                        base_shape.uv,
                        uniform_scale,
                    )
                )

        source_name = source_object.name
        mesh = bpy.data.meshes.new(source_name)
        mesh.from_pydata(
            np.asarray(base_shape.vertices).tolist(),
            [],
            base_shape.faces,
        )
        for face in mesh.polygons:
            face.use_smooth = True
        _assign_uv(mesh, base_shape.uv)
        _assign_float_point_attribute(
            mesh,
            BALLOON_ATTRIBUTE_NAME,
            base_shape.balloon,
        )
        mesh.materials.append(material)
        mesh.update()

        mesh_object = bpy.data.objects.new(source_name, mesh)
        context.collection.objects.link(mesh_object)
        mesh_object.matrix_world = _cutout_world_matrix(
            source_object.matrix_world,
            crop_center,
        )
        if shape == "DEPTH_SYMMETRY":
            mesh_object.matrix_world = (
                mesh_object.matrix_world
                @ Matrix.Rotation(-1.5707963267948966, 4, "Z")
            )
        mesh_object["anyimage_mesh_shape"] = shape
        node_group = load_cutout_node_group("DEPTH_SOLID" if shape == "DEPTH_SYMMETRY" else shape)
        modifier = mesh_object.modifiers.new(name=node_group.name, type="NODES")
        modifier.node_group = node_group
        modifier.show_group_selector = False
        if shape != "DEPTH_SYMMETRY":
            set_modifier_input(
                modifier,
                modifier_input_identifier(
                    node_group,
                    "Thickness",
                    subtype="NONE" if shape in DEPTH_CUTOUT_SHAPES else None,
                ),
                0.0 if shape == "FLAT" else 1.0,
            )
        if shape == "DEPTH_SOLID":
            set_modifier_input(
                modifier,
                modifier_input_identifier(node_group, "Thickness", subtype="DISTANCE"),
                0.2,
            )
        if gesture == "POLYLINE":
            set_modifier_input(
                modifier,
                modifier_input_identifier(node_group, "Mode"),
                1,
            )
            if shape == "SOLID":
                set_modifier_input(
                    modifier,
                    modifier_input_identifier(node_group, "Thickness", subtype="DISTANCE"),
                    0.5,
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
            symmetry_group = load_cutout_node_group("DEPTH_SYMMETRY")
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
