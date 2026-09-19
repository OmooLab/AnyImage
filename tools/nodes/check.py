"""Reload saved assets and evaluate geometry in the target Blender process."""
from math import isfinite
from pathlib import Path

import bpy


ASSET_PATH = Path(__file__).resolve().parents[2] / "src/anyimage/assets/O_AnyImage.blend"
GEOMETRY_NAMES = {
    "O Image Depth Panorama",
    "O Image Plane", "O Image Depth Plane", "O Image Relief Plane",
    "O Image Cutout", "O Image Depth Cutout", "O Image Cutout Symmetry",
}
SHADER_NAMES = {"O Image Layer", "O Image Depth Layer", "O Shadeless"}


def check_asset_library(asset_path):
    """Check library completeness and finite, nonempty evaluated geometry."""
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
        if node_group.name == "O Image Cutout Symmetry":
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


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    check_asset_library(ASSET_PATH)


if __name__ == "__main__":
    main()
