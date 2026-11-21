"""Evaluate the image modifier stack and lay out the baked mesh UVs."""

from contextlib import contextmanager

import numpy as np

from ...common.image_plane import IMAGE_PLANE_NODE_GROUP_NAME
from ...common.image_target import is_image_object
from ..cutout_tool.shape import CUTOUT_NODE_GROUP_NAMES, IMAGE_REGION_ATTRIBUTE_NAME


TARGET_UV = "_anyimage_target_uv"
SINGLE_REGION_GROUPS = frozenset({
    IMAGE_PLANE_NODE_GROUP_NAME, "O Depth Plane", "O Depth Relief",
    "O Depth Panorama",
})
PROTOCOL_ATTRIBUTES = frozenset({
    "o_emission", "o_balloon", "o_normal_reduction", "o_normal_transform", IMAGE_REGION_ATTRIBUTE_NAME,
    "_o_depth_cut", "_o_depth_limit_boundary", "_o_boundary_smooth_weight",
    "_o_boundary_falloff", "_o_cut_boundary", "_o_front_normal", "_o_leaf_id",
    "_o_side_ring_target", "_o_leaf_source_index", "_o_side_base_uv", "_o_side_top_uv",
    "_o_symmetry_weld", "_o_pinned_smooth_boundary", "_o_pinned_smooth_normalization",
    "_o_pinned_smooth_region_point", "_o_pinned_smooth_region_corner",
})


def mesh_bake_modifiers(obj):
    """Return the supported image geometry prefix of the modifier stack."""
    if not is_image_object(obj) or not getattr(obj, "modifiers", None):
        return ()
    first = obj.modifiers[0]
    if first.type != "NODES" or first.node_group is None:
        return ()
    group = first.node_group.name
    if group not in SINGLE_REGION_GROUPS and group not in {
        CUTOUT_NODE_GROUP_NAMES["SOLID"], CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"],
    }:
        return ()
    modifiers = (first,)
    if group == CUTOUT_NODE_GROUP_NAMES["DEPTH_SOLID"] and len(obj.modifiers) > 1:
        second = obj.modifiers[1]
        if (second.type == "NODES" and second.node_group is not None
                and second.node_group.name == CUTOUT_NODE_GROUP_NAMES["DEPTH_SYMMETRY"]):
            modifiers += (second,)
    return modifiers if all(m.show_viewport and m.show_render for m in modifiers) else ()


@contextmanager
def isolate_bake_modifiers(context, obj, modifiers):
    """Evaluate the image prefix and restore subsequent modifier states."""
    states = [(modifier, modifier.show_viewport) for modifier in tuple(obj.modifiers)[len(modifiers):]]
    paths = {modifier.path_from_id("show_viewport") for modifier, _ in states}
    drivers = [(curve, curve.mute) for curve in obj.animation_data.drivers
               if curve.data_path in paths] if obj.animation_data else []
    try:
        for curve, _ in drivers:
            curve.mute = True
        for modifier, _ in states:
            modifier.show_viewport = False
        if states:
            obj.update_tag(refresh={"DATA"})
        yield context.evaluated_depsgraph_get()
    finally:
        for modifier, show_viewport in states:
            modifier.show_viewport = show_viewport
        for curve, mute in drivers:
            curve.mute = mute
        if states:
            obj.update_tag(refresh={"DATA"})
            context.view_layer.update()


def build_layout(mesh, *, single_region=False):
    """Scale and offset source UVs into regular surface tiles."""
    original = mesh.uv_layers.get("UVMap")
    if original is None:
        raise ValueError("The mesh UVMap is missing")
    source_uv = np.empty((len(mesh.loops), 2), dtype=np.float32)
    original.data.foreach_get("uv", source_uv.ravel())
    if not np.isfinite(source_uv).all():
        raise ValueError("The mesh UVMap contains non-finite coordinates")
    if single_region:
        mesh.uv_layers.active = original
        return ((0,),)
    if TARGET_UV in mesh.uv_layers:
        raise ValueError("The mesh contains reserved mesh bake UV names")
    attribute = mesh.attributes.get(IMAGE_REGION_ATTRIBUTE_NAME)
    if attribute is None or attribute.domain != "FACE" or attribute.data_type != "INT":
        raise ValueError("This Cutout lacks surface regions; recreate it from the source image")
    regions = np.empty(len(mesh.polygons), dtype=np.int32)
    attribute.data.foreach_get("value", regions)
    values = np.unique(regions).tolist()
    if not values or not set(values) <= {0, 1, 2, 3}:
        raise ValueError("The Cutout has no supported surface regions")
    bodies = sorted({region // 2 for region in values})
    sides = sorted({region % 2 for region in values}, reverse=True)
    columns, rows = len(bodies), len(sides)
    tiles = tuple(tuple(body * 2 + side if body * 2 + side in values else None
                        for body in bodies) for side in sides)
    loop_counts = np.empty(len(regions), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_counts)
    loop_regions = np.repeat(regions, loop_counts)
    result = np.empty_like(source_uv)
    for region in values:
        loops = loop_regions == region
        local = source_uv[loops]
        if region in (1, 2):
            local[:, 0] = 1 - local[:, 0]
        offset = (bodies.index(region // 2), sides.index(region % 2))
        result[loops] = (local + offset) / (columns, rows)
    target = mesh.uv_layers.new(name=TARGET_UV)
    # Bake in the atlas tangent basis while the shader samples its original render UVs.
    mesh.uv_layers.active = target
    target.data.foreach_set("uv", result.ravel())
    mesh.update()
    return tiles
