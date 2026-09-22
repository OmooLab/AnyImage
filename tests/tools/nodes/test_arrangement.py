"""Exercise automatic arrangement while preserving node programs and geometry."""

import bpy
import numpy as np
import pytest


from tools.nodes.arrangement.arrange import arrange_nodes
from tools.nodes.arrangement.dimensions import estimate_node_dimensions
from tools.nodes.check import ASSET_PATH, SHADER_NAMES
from nodes.groups.image_depth_cutout import build_image_depth_cutout_group
from nodes.groups.image_depth_layer import build_image_depth_layer_group
from nodes.groups.image_layer import build_image_layer_group
from nodes.groups.shadeless import build_shadeless_group


BUILDERS = (
    ("O Image Depth Cutout", build_image_depth_cutout_group),
    ("O Image Layer", build_image_layer_group),
)

SHADER_BUILDERS = {
    "O Image Layer": build_image_layer_group,
    "O Image Depth Layer": build_image_depth_layer_group,
    "O Shadeless": build_shadeless_group,
}


@pytest.fixture(params=[name for name, _ in BUILDERS])
def node_group(request):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return next(builder() for name, builder in BUILDERS if name == request.param)


def _source(socket):
    while socket.node.bl_idname == "NodeReroute":
        socket = socket.node.inputs[0].links[0].from_socket
    node = socket.node
    return ("INPUT" if node.bl_idname == "NodeGroupInput" else node.name, socket.identifier)


def _value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bpy.types.ID):
        return value.as_pointer()
    return tuple(value)


def _program(node_group):
    nodes = {}
    for node in node_group.nodes:
        if node.bl_idname in {"NodeReroute", "NodeGroupInput", "NodeFrame"}:
            continue
        settings = {
            name: _value(getattr(node, name))
            for name in ("operation", "data_type", "input_type", "domain", "mode", "clamp",
                         "interpolation", "interpolation_type", "extension", "pattern_mode",
                         "space", "uv_map", "attribute_type", "attribute_name", "rotation_type",
                         "invert", "blend_type", "clamp_factor", "clamp_result", "distribution")
            if hasattr(node, name)
        }
        if hasattr(node, "mapping"):
            mapping = node.mapping
            settings["mapping"] = (
                mapping.extend, mapping.use_clip,
                tuple((tuple(point.location), point.handle_type)
                      for curve in mapping.curves for point in curve.points),
            )
        inputs = [
            (socket.identifier, _value(socket.default_value) if hasattr(socket, "default_value") else None,
             [_source(link.from_socket) for link in sorted(
                 socket.links, key=lambda link: link.multi_input_sort_id, reverse=True)])
            for socket in node.inputs
        ]
        paired = getattr(node, "paired_output", None)
        nodes[node.name] = (node.bl_idname, settings, inputs, paired.name if paired else None)
    interface = [
        (item.identifier, item.name, item.in_out, item.socket_type,
         _value(item.default_value) if hasattr(item, "default_value") else None)
        for item in node_group.interface.items_tree if item.item_type == "SOCKET"
    ]
    return nodes, interface


def _surface(node_group):
    mesh = bpy.data.meshes.new("Layout Surface")
    mesh.from_pydata(
        [(x - 2, y - 1, 0) for y in range(3) for x in range(5)], [],
        [(y * 5 + x, y * 5 + x + 1, (y + 1) * 5 + x + 1, (y + 1) * 5 + x)
         for y in range(2) for x in range(4)],
    )
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        x, y, _ = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = ((x + 2) / 4, (y + 1) / 2)
    profile = mesh.attributes.new("o_balloon", "FLOAT", "POINT")
    for vertex, value in zip(mesh.vertices, profile.data):
        value.value = 0.25 * (1 - abs(vertex.co.x) / 2) * (1 - abs(vertex.co.y))
    mesh.materials.append(bpy.data.materials.new("Image"))
    obj = bpy.data.objects.new("Layout Surface", mesh)
    bpy.context.collection.objects.link(obj)
    modifier = obj.modifiers.new("Surface", "NODES")
    modifier.node_group = node_group
    image = bpy.data.images.new("Layout Depth", width=16, height=8, float_buffer=True)
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    yy, xx = np.mgrid[:8, :16]
    pixels = np.ones((8, 16, 4), dtype=np.float32)
    pixels[..., 0] = ((xx + 0.5) / 16 - 0.5) * 4
    pixels[..., 1] = -((yy + 0.5) / 8 - 0.5) * 2
    pixels[..., 2] = 2 + xx * 0.02
    image.pixels.foreach_set(pixels.ravel())
    values = {"Subdivide": 1, "Thickness": 0.2, "Depth Image": image,
              "Uniform Scale": 1.0, "Reference Depth": 2.5, "Depth Scale": 0.8,
              "Edge Turn": 1, "Depth Split": 0.25,
              "Offset": 0.5}
    mode = None
    for item in node_group.interface.items_tree:
        if item.item_type != "SOCKET" or item.in_out != "INPUT":
            continue
        if item.name in values:
            modifier[item.identifier] = values[item.name]
        elif item.name == "Mode":
            mode = item.identifier

    def evaluate():
        results = []
        for choice in range(2 if mode else 1):
            if mode:
                modifier[mode] = choice
            obj.update_tag(refresh={"DATA"})
            bpy.context.view_layer.update()
            result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            evaluated = result.to_mesh()
            try:
                assert len(evaluated.vertices) > 0
                results.append((np.array([vertex.co[:] for vertex in evaluated.vertices]),
                                [tuple(face.vertices) for face in evaluated.polygons]))
            finally:
                result.to_mesh_clear()
        return results

    return evaluate


def test_arrangement_preserves_program_and_evaluation(node_group):
    program = _program(node_group)
    evaluate = _surface(node_group) if node_group.bl_idname == "GeometryNodeTree" else list
    geometry = evaluate()
    arrange_nodes(node_group)
    assert _program(node_group) == program
    for (before_points, before_faces), (after_points, after_faces) in zip(geometry, evaluate()):
        np.testing.assert_allclose(after_points, before_points, atol=1e-6)
        assert after_faces == before_faces

    display_nodes = [node for node in node_group.nodes if node.bl_idname not in {"NodeFrame", "NodeReroute"}]
    boxes = []
    for node in display_nodes:
        size = estimate_node_dimensions(node)
        x, y = node.location_absolute
        box = (x, y - size.height, x + size.width, y)
        assert all(not (box[0] < other[2] and box[2] > other[0]
                        and box[1] < other[3] and box[3] > other[1]) for other in boxes), node.name
        boxes.append(box)


@pytest.mark.parametrize("name", sorted(SHADER_NAMES))
def test_shader_asset_preserves_definition(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    definition = SHADER_BUILDERS[name]()
    expected = _program(definition)
    with bpy.data.libraries.load(str(ASSET_PATH)) as (_, target):
        target.node_groups = [name]
    assert _program(target.node_groups[0]) == expected
