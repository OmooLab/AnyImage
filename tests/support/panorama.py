"""Build a radial depth panorama for geometry and baking tests."""

import bpy
import numpy as np
from anyimage.common.object import modifier_input_identifier, set_modifier_input
from nodes.groups.image_depth_panorama import build_image_depth_panorama_group


def panorama(depth=3, alpha=1, subdivide=3):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    group = build_image_depth_panorama_group()
    image = bpy.data.images.new("Radial Depth", width=128, height=64, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    rgba = np.ones((64, 128, 4), np.float32)
    rgba[..., :3] = np.broadcast_to(depth, (64, 128))[..., None]
    rgba[..., 3] = alpha
    image.pixels.foreach_set(rgba.ravel())
    obj = bpy.data.objects.new("Panorama", bpy.data.meshes.new("Panorama"))
    bpy.context.collection.objects.link(obj)
    modifier = obj.modifiers.new("Panorama", "NODES")
    modifier.node_group = group

    def set_value(name, value):
        set_modifier_input(modifier, modifier_input_identifier(group, name), value)
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()

    for name, value in (("Depth Image", image), ("Subdivide", subdivide)):
        set_value(name, value)
    set_value("Boundary Smooth", 0)
    set_value("Depth Split", 0)
    return obj, set_value


def evaluated(obj):
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = result.to_mesh()
    try:
        points = np.array([v.co[:] for v in mesh.vertices]).reshape(-1, 3)
        faces = [tuple(f.vertices) for f in mesh.polygons]
        uv = np.array([v.uv[:] for v in mesh.uv_layers.active.data]) if mesh.uv_layers.active else np.empty((0, 2))
        return points, faces, uv
    finally:
        result.to_mesh_clear()
