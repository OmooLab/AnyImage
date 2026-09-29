import bpy
import numpy as np


from anyimage.common import image as image_data
from anyimage.common.selection import SelectionMask
from anyimage.operators.cutout_tool import geometry as cutout_geometry
from anyimage.operators.cutout_tool import object as cutout_object
from tests.support.color_image import color_image as prepared_color_image


def _inputs(group):
    return [
        item.name
        for item in group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    ]


def _group_node(group, node_tree):
    return next(
        node
        for node in node_tree.nodes
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree == group
    )


def _create_cutout_shape(
    source,
    shape,
    edge_length,
    *,
    bounds=None,
    depth_image=None,
    depth_metadata=None,
    selection_values=None,
    gesture="LASSO",
):
    if bounds is None:
        bounds = (0, 0, *tuple(int(value) for value in source.data.size))
    left, top, right, bottom = bounds
    if selection_values is None:
        selection_values = np.ones((bottom - top, right - left), dtype=np.float32)
    selection_mask = SelectionMask(selection_values, bounds)
    source_rgba = image_data.image_rgba(source.data)
    color_image = prepared_color_image(
        source.data,
        selection_mask.bounds,
        source_rgba,
    )
    base_shape = cutout_geometry.build_base_shape(
        bpy.context,
        source,
        edge_length,
        selection_mask.values,
        selection_mask.bounds,
    )
    return cutout_object.create_shape_object(
        bpy.context,
        source,
        shape,
        selection_mask.values,
        selection_mask.bounds,
        base_shape,
        depth_image=depth_image,
        depth_metadata=depth_metadata,
        gesture=gesture,
        color_image=color_image,
    )


def _depth_image(points, alpha, name="Depth"):
    points = np.asarray(points, dtype=np.float32)
    alpha = np.asarray(alpha, dtype=np.float32)
    height, width = alpha.shape
    pixels = np.zeros((height, width, 4), dtype=np.float32)
    pixels[..., :3] = points
    pixels[..., 3] = alpha
    image = bpy.data.images.new(
        name,
        width=width,
        height=height,
        alpha=True,
        float_buffer=True,
    )
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    image.pixels.foreach_set(np.flipud(pixels).ravel())
    image.pack()
    return image


def _depth_metadata(intrinsics, image_size):
    return {
        "intrinsics": tuple(tuple(float(value) for value in row) for row in intrinsics),
        "image_size": tuple(int(value) for value in image_size),
    }


def _evaluated_positions(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result = evaluated.to_mesh()
    try:
        return np.asarray([tuple(vertex.co) for vertex in result.vertices])
    finally:
        evaluated.to_mesh_clear()


