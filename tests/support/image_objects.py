import bpy
import numpy as np


from anyimage.common.image import image_rgba
from anyimage.common.selection import SelectionMask
from anyimage.operators.cutout_tool.object import create_cutout_shape


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
    intrinsics=None,
    selection_values=None,
    gesture="LASSO",
):
    if bounds is None:
        bounds = (0, 0, *tuple(int(value) for value in source.data.size))
    left, top, right, bottom = bounds
    if selection_values is None:
        selection_values = np.ones((bottom - top, right - left), dtype=np.float32)
    return create_cutout_shape(
        bpy.context, source, shape, edge_length, SelectionMask(selection_values, bounds),
        source_rgba=image_rgba(source.data),
        depth_image=depth_image,
        intrinsics=intrinsics,
        gesture=gesture,
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


def _evaluated_positions(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result = evaluated.to_mesh()
    try:
        return np.asarray([tuple(vertex.co) for vertex in result.vertices])
    finally:
        evaluated.to_mesh_clear()




def packed_clipboard_image(data, suffix):
    from anyimage.operators.clipboard_image.cache import clipboard_source

    with clipboard_source(data, suffix) as image:
        if image.packed_file:
            return image, True
        image.pack()
        image.use_fake_user = True
    image.use_fake_user = False
    return image, False
