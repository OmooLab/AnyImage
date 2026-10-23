"""Create and bake a bounded volume from panorama emission."""

from math import ceil, floor, isclose

import bpy
import numpy as np
from mathutils import Matrix, Vector


def panorama_probe_bounds(context, panorama, max_distance):
    """Return world center, size and resolution from evaluated geometry."""
    evaluated = panorama.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        if not mesh.polygons:
            return None
        positions = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", positions)
        transform = np.asarray(panorama.matrix_world)
        positions = positions.reshape(-1, 3) @ transform[:3, :3].T
        positions *= context.scene.unit_settings.scale_length
        if not np.isfinite(positions).all():
            return None
        lower = np.maximum(positions.min(axis=0), -max_distance)
        upper = np.minimum(positions.max(axis=0), max_distance)
    finally:
        evaluated.to_mesh_clear()
    if np.any(lower > upper):
        return None
    center, size, resolution = [], [], []
    for low, high in zip(lower, upper):
        length = high - low
        if isclose(length, round(length), abs_tol=1e-5):
            length = round(length)
        extent = min(max(ceil(length), 1), 2 * max_distance)
        midpoint = min(max((low + high) / 2, -max_distance + extent / 2),
                       max_distance - extent / 2)
        center.append(midpoint)
        size.append(extent)
        resolution.append(min(max(floor(length), 1), 256))
    unit = context.scene.unit_settings.scale_length
    return (panorama.matrix_world.translation + Vector(center) / unit,
            Vector(size) / unit, resolution)


def create_panorama_light_probe(context, panorama, max_distance):
    """Create a parented volume, or return None for an empty capture region."""
    bounds = panorama_probe_bounds(context, panorama, max_distance)
    if bounds is None:
        return None
    center, size, resolution = bounds
    data = bpy.data.lightprobes.new(f"{panorama.name}_LightProbe", "VOLUME")
    probe = None
    try:
        data.capture_indirect = False
        data.capture_emission = True
        data.capture_world = False
        data.clamp_direct = 50.0
        data.resolution_x, data.resolution_y, data.resolution_z = resolution
        probe = bpy.data.objects.new(data.name, data)
        context.collection.objects.link(probe)
        probe.parent = panorama
        probe.matrix_parent_inverse = panorama.matrix_world.inverted_safe()
        probe.matrix_world = Matrix.LocRotScale(center, None, size / 2)
        return probe
    except Exception:
        if probe is not None:
            bpy.data.objects.remove(probe, do_unlink=True)
        bpy.data.lightprobes.remove(data)
        raise


def bake_panorama_light_probe(context, panorama, probe):
    """Synchronously bake only panorama emission and restore scene state."""
    scene = context.scene
    visibility = [(obj, obj.hide_render) for obj in scene.objects]
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    engine = scene.render.engine
    hidden = panorama.hide_probe_volume
    try:
        for obj, _ in visibility:
            obj.hide_render = obj not in (panorama, probe)
        panorama.hide_probe_volume = False
        for obj in selected:
            obj.select_set(False)
        probe.select_set(True)
        context.view_layer.objects.active = probe
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        context.view_layer.update()
        if bpy.ops.object.lightprobe_cache_bake("EXEC_DEFAULT", subset="ACTIVE") != {"FINISHED"}:
            raise RuntimeError("Panorama light probe bake cancelled")
    finally:
        for obj, hide_render in visibility:
            obj.hide_render = hide_render
        panorama.hide_probe_volume = hidden
        scene.render.engine = engine
        probe.select_set(False)
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = active
