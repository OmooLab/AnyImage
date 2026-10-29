import bpy
import pytest

from anyimage.common.node import load_node_group


@pytest.mark.parametrize("group_name", ["O Shadeless", "O Image Depth Panorama"])
@pytest.mark.skipif(bpy.app.version >= (5, 0, 0), reason="Append behavior before Blender 5.0")
def test_appended_groups_are_not_assets(group_name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    user_asset = bpy.data.node_groups.new("User Asset", "GeometryNodeTree")
    user_asset.asset_mark()
    try:
        group = load_node_group(group_name)

        assert group.asset_data is None
        assert group.use_fake_user
        assert all(
            tree.asset_data is None and tree.library is None and tree.is_editable
            for tree in bpy.data.node_groups
            if tree != user_asset
        )
        assert user_asset.asset_data is not None
        assert load_node_group(group_name) == group
        assert load_node_group(user_asset.name) == user_asset
        assert user_asset.asset_data is not None
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)


def test_loaded_groups_reuse_nested_dependencies():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        plane = load_node_group("O Image Plane")
        depth_plane = load_node_group("O Image Depth Plane")

        assert any(
            node.type == "GROUP" and node.node_tree == plane
            for node in depth_plane.nodes
        )
        assert set(bpy.data.node_groups) == {plane, depth_plane}
        assert load_node_group(depth_plane.name) == depth_plane
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)
