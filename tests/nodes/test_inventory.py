"""Check the saved library's public inventory and persistence."""
from math import isfinite

import bpy
import pytest
from anyimage.common.node import node_asset_path


GEOMETRY_NAMES = {
    "O Depth Panorama",
    "O Plane", "O Depth Plane", "O Depth Relief",
    "O Cutout", "O Depth Cutout", "O Cutout Symmetry",
}
SHADER_NAMES = {"O Texture to Layer", "O Shadeless", "O Background", "O World Vector"}


def test_saved_assets_evaluate():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    asset_path = node_asset_path()
    with bpy.data.libraries.load(str(asset_path), link=True) as (source, target):
        assert set(source.node_groups) == GEOMETRY_NAMES | SHADER_NAMES
        target.node_groups = sorted(GEOMETRY_NAMES | SHADER_NAMES)
    pending, checked = list(target.node_groups), set()
    while pending:
        group = pending.pop()
        if group in checked or group.bl_idname != "GeometryNodeTree":
            continue
        checked.add(group)
        for node in group.nodes:
            assert node.bl_idname != "GeometryNodeCaptureAttribute", group.name
            if node.bl_idname == "GeometryNodeGroup" and node.node_tree:
                pending.append(node.node_tree)
    depth_image = bpy.data.images.new("Asset Check Depth", width=8, height=8, float_buffer=True)
    depth_image.colorspace_settings.name = "Non-Color"
    depth_image.pixels.foreach_set([
        value for y in range(8) for x in range(8)
        for value in ((x + 0.5) / 8 - 0.5, (y + 0.5) / 8 - 0.5, 2.0, 1.0)
    ])
    for node_group in target.node_groups:
        expected_type = "GeometryNodeTree" if node_group.name in GEOMETRY_NAMES else "ShaderNodeTree"
        assert node_group.bl_idname == expected_type and node_group.library is not None, node_group.name
        if expected_type == "ShaderNodeTree":
            continue
        mesh = bpy.data.meshes.new("Asset Check Plane")
        mesh.from_pydata(
            [(x / 3 - 0.5, 0, y / 3 - 0.5) for y in range(4) for x in range(4)], [],
            [(y * 4 + x, y * 4 + x + 1, (y + 1) * 4 + x + 1, (y + 1) * 4 + x)
             for y in range(3) for x in range(3)],
        )
        uv = mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            position = mesh.vertices[loop.vertex_index].co
            uv.data[loop.index].uv = (position.x + 0.5, position.z + 0.5)
        profile = mesh.attributes.new("o_balloon", "FLOAT", "POINT")
        for value in profile.data:
            value.value = 0.2
        obj = bpy.data.objects.new("Asset Check", mesh)
        bpy.context.collection.objects.link(obj)
        modifier = obj.modifiers.new("Asset Check", "NODES")
        modifier.node_group = node_group
        values = {"Subdivide": 0, "Thickness": 0.2, "Reference Depth": 2.0,
                  "Depth Image": depth_image, "Uniform Scale": 1.0, "Depth Split": 0.0}
        if node_group.name == "O Cutout Symmetry":
            values["Offset"] = 0.5
        for item in node_group.interface.items_tree:
            if item.item_type == "SOCKET" and item.in_out == "INPUT" and item.name in values:
                modifier[item.identifier] = values[item.name]
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        result = evaluated.to_mesh()
        try:
            assert len(result.vertices) and len(result.polygons), node_group.name
            assert all(isfinite(value) for vertex in result.vertices for value in vertex.co), node_group.name
            assert not list(modifier.node_warnings), (
                node_group.name, [warning.message for warning in modifier.node_warnings],
            )
            assert not any(
                "o_anyimage" in attribute.name for attribute in result.attributes
            ), node_group.name
            assert not any(
                attribute.name.startswith("_o_") for attribute in result.attributes
            ), node_group.name
        finally:
            evaluated.to_mesh_clear()
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
    bpy.data.images.remove(depth_image)
    print(f"Checked {len(target.node_groups)} saved node groups in Blender {bpy.app.version_string}")


def test_saved_parameter_interfaces_match_definitions():
    from omoonodes.assets import Library
    from tests.support.paths import PROJECT_ROOT

    parameters = {
        "O Plane": {"Subdivide"},
        "O Depth Plane": {"Subdivide", "Thickness", "Depth Split", "Depth Limit", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Depth Relief": {"Subdivide", "Thickness", "Depth Direction", "Depth Offset"},
        "O Cutout": {"Thickness"},
        "O Depth Cutout": {"Thickness", "Depth Split", "Boundary Smooth", "Rear Smooth", "Normal Bias", "Front Inflation", "Depth Limit"},
        "O Cutout Symmetry": {"Direction", "Offset", "Scale", "Fill Sides", "Smooth"},
        "O Depth Panorama": {"Subdivide", "Depth Scale", "Depth Split", "Dome Radius", "Horizon Bend", "Depth Mask", "Mask Threshold", "Boundary Smooth"},
        "O Background": {"Color", "Strength", "Light", "Transmission (Cycles)"},
        "O World Vector": {"Rotation", "Blur", "Horizon Bend"},
        "O Texture to Layer": {"Alpha Scale", "Alpha Background", "Roughness Scale", "Roughness Contrast", "Highlight Threshold", "Normal Scale", "Bump Scale", "Object Space"},
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
            for item in inputs:
                if item.name == "Subdivide":
                    assert (item.min_value, item.max_value) == (0, 8), group.name
            if group.name == "O Depth Cutout":
                names = [item.name for item in inputs]
                assert "Side Roundness" not in names and "Edge Turn" not in names
                controls = {item.name: item for item in inputs}
                bias = controls["Normal Bias"]
                assert (bias.default_value, bias.min_value, bias.max_value) == (0, -2, 2)
                assert controls["Rear Smooth"].default_value == 8
                smooth = controls["Boundary Smooth"]
                assert (smooth.default_value, smooth.min_value, smooth.max_value) == (4, 0, 16)
                thicknesses = [item for item in inputs if item.name == "Thickness"]
                assert len(thicknesses) == 2
                assert {item.subtype: item.default_value for item in thicknesses} == pytest.approx({"NONE": 1.0, "DISTANCE": 0.1})
                inflation = next(item for item in inputs if item.name == "Front Inflation")
                thickness = next(item for item in inputs if item.name == "Thickness" and item.subtype == "NONE")
                assert not inflation.parent.name
                assert abs(inflation.default_value - 0.2) < 1e-6
                assert inputs.index(inflation) == inputs.index(thickness) + 1
                split = next(item for item in inputs if item.name == "Depth Split")
                limit = next(item for item in inputs if item.name == "Depth Limit")
                assert not limit.parent.name
                assert limit.min_value == -1.0
                assert inputs.index(limit) == inputs.index(split) + 1
            elif group.name == "O Texture to Layer":
                controls = {item.name: item for item in inputs}
                for name in ("Color Texture", "Alpha Texture", "Normal Texture"):
                    assert controls[name].hide_value, name
            elif group.name == "O World Vector":
                assert [item.name for item in inputs] == ["Rotation", "Blur", "Horizon Bend"]
                assert inputs[0].subtype == "EULER"
                assert tuple(inputs[0].default_value) == (0, 0, 0)
                assert (inputs[1].default_value, inputs[1].min_value, inputs[1].max_value) == (0, 0, 1)
                assert (inputs[2].default_value, inputs[2].min_value, inputs[2].max_value) == (0, -1, 1)
            elif group.name == "O Cutout Symmetry":
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
                    tuple(item.default_value) if item.socket_type in {"NodeSocketVector", "NodeSocketColor"} else item.default_value,
                    getattr(item, "min_value", None), getattr(item, "max_value", None),
                    getattr(item, "subtype", None),
                )
                for item in sockets
            ]
        assert result.keys() == parameters.keys()
        return result

    bpy.ops.wm.read_factory_settings(use_empty=True)
    expected = interfaces(list(Library(PROJECT_ROOT / "nodes/O_AnyImage").build()))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(node_asset_path())) as (library, target):
        target.node_groups = list(library.node_groups)
    actual = interfaces(target.node_groups)
    for name in expected:
        assert actual[name] == expected[name], (name, actual[name], expected[name])


def test_geometry_nodes_contribute_to_output():
    from omoonodes.assets import Library
    from tests.support.paths import PROJECT_ROOT

    bpy.ops.wm.read_factory_settings(use_empty=True)
    groups = list(Library(PROJECT_ROOT / "nodes/O_AnyImage").build())
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
    from omoonodes.assets import Library
    from tests.support.paths import PROJECT_ROOT

    bpy.ops.wm.read_factory_settings(use_empty=True)
    pending = list(Library(PROJECT_ROOT / "nodes/O_AnyImage").build())
    seen = set()
    allowed = {
        "UVMap": ("FLOAT2", "CORNER"),
        "o_balloon": ("FLOAT", "POINT"),
        "o_emission": ("FLOAT", "CORNER"),
        "o_image_region": ("INT", "FACE"),
        "o_normal_transform": ("FLOAT_VECTOR", "FACE"),
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
        "_o_pinned_smooth_weight_point": ("FLOAT", "POINT"),
        "_o_pinned_smooth_weight_corner": ("FLOAT", "CORNER"),
        "_o_pinned_smooth_region_point": ("FLOAT", "POINT"),
        "_o_pinned_smooth_region_corner": ("FLOAT", "CORNER"),
        "_o_side_base_uv": ("FLOAT_VECTOR", "POINT"),
        "_o_side_top_uv": ("FLOAT_VECTOR", "POINT"),
        "_o_symmetry_weld": ("BOOLEAN", "FACE"),
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
                assert node.data_type == "FLOAT" and node.domain in {"POINT", "FACE", "CORNER"}
            else:
                assert name in allowed, (group.name, name)
                assert (node.data_type, node.domain) == allowed[name]
    assert {group.name for group in seen} == GEOMETRY_NAMES
