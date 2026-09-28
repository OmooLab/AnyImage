"""Check the saved library's public inventory and persistence."""
import bpy
import pytest
from anyimage.common.node import node_asset_path
from tools.nodes.check import GEOMETRY_NAMES


def test_saved_assets_evaluate():
    from tools.nodes.check import check_asset_library

    bpy.ops.wm.read_factory_settings(use_empty=True)
    check_asset_library(node_asset_path())


def test_saved_parameter_interfaces_match_definitions():
    from tools.nodes.build import build_node_groups

    parameters = {
        "O Image Plane": {"Subdivide"},
        "O Image Depth Plane": {"Subdivide", "Thickness", "Depth Split", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Image Relief Plane": {"Subdivide", "Thickness", "Depth Direction", "Depth Offset"},
        "O Image Cutout": {"Thickness"},
        "O Image Depth Cutout": {"Thickness", "Depth Split", "Boundary Smooth", "Rear Smooth", "Normal Bias", "Front Inflation", "Depth Limit"},
        "O Image Cutout Symmetry": {"Direction", "Offset", "Scale", "Fill Sides", "Smooth"},
        "O Image Depth Panorama": {"Subdivide", "Depth Scale", "Depth Split", "Dome Radius", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Image Layer": {"Alpha Fix", "Normal Scale", "Bump Scale", "Object Space"},
        "O Image Depth Layer": {"Bump Scale"},
    }

    def interfaces(groups):
        result = {}
        for group in groups:
            if group.name not in parameters:
                continue
            inputs = [
                item for item in group.interface.items_tree
                if item.item_type == "SOCKET" and item.in_out == "INPUT"
            ]
            if group.name == "O Image Depth Cutout":
                names = [item.name for item in inputs]
                assert "Side Roundness" not in names and "Edge Turn" not in names
                controls = {item.name: item for item in inputs}
                bias = controls["Normal Bias"]
                assert (bias.default_value, bias.min_value, bias.max_value) == (0, -2, 2)
                assert controls["Rear Smooth"].default_value == 8
                smooth = controls["Boundary Smooth"]
                assert (smooth.default_value, smooth.min_value, smooth.max_value) == (4, 0, 16)
                thicknesses = [item for item in inputs if item.name == "Thickness"]
                assert len(thicknesses) == 2 and all(item.default_value == 0 for item in thicknesses)
                inflation = next(item for item in inputs if item.name == "Front Inflation")
                thickness = next(item for item in inputs if item.name == "Thickness" and item.subtype == "NONE")
                assert not inflation.parent.name
                assert abs(inflation.default_value - 0.3) < 1e-6
                assert inputs.index(inflation) == inputs.index(thickness) + 1
                split = next(item for item in inputs if item.name == "Depth Split")
                limit = next(item for item in inputs if item.name == "Depth Limit")
                assert not limit.parent.name
                assert limit.min_value == -1.0
                assert inputs.index(limit) == inputs.index(split) + 1
            elif group.name == "O Image Cutout Symmetry":
                assert [item.name for item in inputs] == [
                    "Geometry", "Direction", "Offset", "Scale", "Fill Sides", "Smooth",
                ]
                assert tuple(inputs[1].default_value) == (0, 0, 1)
                for item, expected in zip(inputs[2:], [(0, -10, 10), (1, 0, 2), (True,), (4, 0, 16)]):
                    values = tuple(getattr(item, key) for key in ("default_value", "min_value", "max_value")
                                   if hasattr(item, key))
                    assert values == pytest.approx(expected)
            sockets = [
                item for item in inputs if item.name in parameters[group.name]
            ]
            assert {item.name for item in sockets} == parameters[group.name]
            assert all(item.description for item in sockets), group.name
            result[group.name] = [
                (
                    inputs.index(item), item.identifier, item.name, item.description,
                    item.parent.name, item.socket_type,
                    tuple(item.default_value) if item.socket_type == "NodeSocketVector" else item.default_value,
                    getattr(item, "min_value", None), getattr(item, "max_value", None),
                    getattr(item, "subtype", None),
                )
                for item in sockets
            ]
        assert result.keys() == parameters.keys()
        return result

    bpy.ops.wm.read_factory_settings(use_empty=True)
    expected = interfaces(build_node_groups())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(node_asset_path())) as (library, target):
        target.node_groups = list(library.node_groups)
    assert interfaces(target.node_groups) == expected


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
        "_o_depth_limit_boundary": ("BOOLEAN", "POINT"),
        "_o_boundary_smooth_weight": ("FLOAT", "POINT"),
        "_o_boundary_falloff": ("FLOAT", "POINT"),
        "_o_cut_boundary": ("BOOLEAN", "POINT"),
        "_o_front_normal": ("FLOAT_VECTOR", "POINT"),
        "_o_leaf_id": ("INT", "POINT"),
        "_o_side_ring_target": ("FLOAT_VECTOR", "POINT"),
        "_o_leaf_source_index": ("INT", "POINT"),
        "_o_pinned_smooth_boundary": ("BOOLEAN", "POINT"),
        "_o_pinned_smooth_normalization": ("FLOAT", "POINT"),
        "_o_pinned_smooth_region_point": ("FLOAT", "POINT"),
        "_o_pinned_smooth_region_corner": ("FLOAT", "CORNER"),
        "_o_side_base_uv": ("FLOAT_VECTOR", "POINT"),
        "_o_side_top_uv": ("FLOAT_VECTOR", "POINT"),
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
