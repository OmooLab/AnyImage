"""Create Blender data for a Cutout Shape."""

from .ai_shape import DEPTH_CUTOUT_SHAPES
from .shape import CUTOUT_NODE_GROUP_NAMES
from .object import create_cutout_modifier
from .mesh_object import create_cutout_mesh

from enum import StrEnum

import bpy

from ...common.coordinate import canonical_direction_to_symmetry_legacy
from ...common.geometry_image import (
    DEPTH_LIMIT_MEDIAN_FACTOR,
    depth_uniform_scale,
    fit_symmetry_depth_direction,
    median_depth,
    reference_depth,
)
from ...common.material import create_image_material
from ...common.object import (
    finalize_object_result,
    modifier_input_identifier,
    set_modifier_input,
)
from ...common.node import load_node_group
from .geometry import (
    build_reference_mask,
    crop_plane_bounds,
)


class NormalMode(StrEnum):
    NONE = "NONE"
    TANGENT = "TANGENT"
    OBJECT = "OBJECT"


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
    from mathutils import Matrix

    normal_mode = NormalMode.OBJECT if shape in DEPTH_CUTOUT_SHAPES else NormalMode(normal_mode)
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
            normal_space=(
                NormalMode.TANGENT.value if normal_mode == NormalMode.NONE else normal_mode.value
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
                depth_direction = canonical_direction_to_symmetry_legacy(
                    fit_symmetry_depth_direction(
                        depth_image,
                        base_shape.vertices,
                        base_shape.uv,
                        uniform_scale,
                    )
                )

        mesh_object = create_cutout_mesh(
            context, source_object, content_bounds, base_shape, material
        )
        mesh = mesh_object.data
        if shape == "DEPTH_SYMMETRY":
            mesh_object.matrix_world = mesh_object.matrix_world @ Matrix.Rotation(
                -1.5707963267948966, 4, "Z"
            )
        mesh_object["o_image_object"] = True
        node_group = load_cutout_node_group("DEPTH_SOLID" if shape == "DEPTH_SYMMETRY" else shape)
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
