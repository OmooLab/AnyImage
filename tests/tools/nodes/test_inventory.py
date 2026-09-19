"""Check the saved library's public inventory and persistence."""
import bpy
from anyimage.common.node import node_asset_path
from tools.nodes.check import GEOMETRY_NAMES


def test_saved_assets_evaluate():
    from tools.nodes.check import check_asset_library

    bpy.ops.wm.read_factory_settings(use_empty=True)
    check_asset_library(node_asset_path())


def test_saved_parameter_descriptions_match_definitions():
    from tools.nodes.build import build_node_groups

    parameters = {
        "O Image Plane": {"Subdivide"},
        "O Image Depth Plane": {"Subdivide", "Thickness", "Depth Split", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Image Relief Plane": {"Subdivide", "Thickness", "Depth Direction", "Depth Offset"},
        "O Image Cutout": {"Thickness"},
        "O Image Depth Cutout": {"Thickness", "Depth Split", "Boundary Smooth", "Edge Turn", "Front Inflation"},
        "O Image Cutout Symmetry": {"Direction", "Offset", "Scale", "Fill Sides", "Smooth"},
        "O Image Depth Panorama": {"Subdivide", "Depth Scale", "Depth Split", "Dome Radius", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Image Layer": {"Alpha Fix", "Normal Scale", "Bump Scale", "Object Space"},
        "O Image Depth Layer": {"Bump Scale"},
    }

    def descriptions(groups):
        result = {}
        for group in groups:
            if group.name not in parameters:
                continue
            sockets = [
                item for item in group.interface.items_tree
                if item.item_type == "SOCKET" and item.in_out == "INPUT"
                and item.name in parameters[group.name]
            ]
            assert {item.name for item in sockets} == parameters[group.name]
            assert all(item.description for item in sockets), group.name
            result[group.name] = [(item.identifier, item.name, item.description) for item in sockets]
        assert result.keys() == parameters.keys()
        return result

    bpy.ops.wm.read_factory_settings(use_empty=True)
    expected = descriptions(build_node_groups())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(node_asset_path())) as (library, target):
        target.node_groups = list(library.node_groups)
    assert descriptions(target.node_groups) == expected


def test_geometry_nodes_contribute_to_output():
    from tools.nodes.build import build_node_groups

    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = build_node_groups()
    for group in groups:
        if group.bl_idname != "GeometryNodeTree":
            continue
        pending = [node for node in group.nodes if node.bl_idname == "NodeGroupOutput"]
        used = set()
        while pending:
            node = pending.pop()
            if node in used:
                continue
            used.add(node)
            pending.extend(link.from_node for socket in node.inputs for link in socket.links)
            pending.extend(candidate for candidate in group.nodes
                           if getattr(candidate, "paired_output", None) == node)
        unused = [node.name for node in group.nodes
                  if node not in used and node.bl_idname != "NodeFrame"]
        assert not unused, (group.name, unused)


def test_geometry_attribute_contract_includes_nested_groups():
    from tools.nodes.build import build_node_groups

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pending = build_node_groups()
    seen = set()
    allowed = {
        "UVMap": ("FLOAT2", "CORNER"),
        "o_balloon": ("FLOAT", "POINT"),
        "_o_depth_cut": ("BOOLEAN", "CORNER"),
            "_o_front_normal": ("FLOAT_VECTOR", "POINT"),
        "_o_symmetry_weld": ("BOOLEAN", "FACE"),
        "o_depth_rotation": ("FLOAT_VECTOR", "FACE"),
        "o_depth_face": ("FLOAT", "FACE"),
        "o_depth_axis": ("FLOAT", "FACE"),
    }
    while pending:
        group = pending.pop()
        if group in seen or group.bl_idname != "GeometryNodeTree":
            continue
        seen.add(group)
        for node in group.nodes:
            assert node.bl_idname != "GeometryNodeCaptureAttribute", group.name
            if node.bl_idname == "GeometryNodeGroup" and node.node_tree:
                pending.append(node.node_tree)
            if node.bl_idname != "GeometryNodeStoreNamedAttribute":
                continue
            name = node.inputs["Name"].default_value
            if name == "o_normal_reduction":
                assert node.data_type == "FLOAT" and node.domain in {"POINT", "FACE"}
            else:
                assert name in allowed, (group.name, name)
                assert (node.data_type, node.domain) == allowed[name]
    assert {group.name for group in seen} == GEOMETRY_NAMES
