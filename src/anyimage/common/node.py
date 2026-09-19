from pathlib import Path

import bpy


NODE_ASSET_NAME = "O_AnyImage.blend"


def node_asset_path():
    return Path(__file__).resolve().parents[1] / "assets" / NODE_ASSET_NAME


def load_node_group(group_name):
    existing = bpy.data.node_groups.get(group_name)
    if existing is not None:
        return existing

    asset_path = node_asset_path()
    if not asset_path.is_file():
        raise RuntimeError(f"Missing node asset: {asset_path}")
    if bpy.app.version < (5, 0, 0):
        directory = str(asset_path) + "/NodeTree/"
        result = bpy.ops.wm.append(
            filepath=directory + group_name,
            directory=directory,
            filename=group_name,
            link=False,
            do_reuse_local_id=False,
        )
        if "FINISHED" not in result:
            raise RuntimeError("Unable to append the node asset")
        node_group = bpy.data.node_groups.get(group_name)
        if node_group is None:
            raise RuntimeError("Appended node asset is unavailable")
        node_group.use_fake_user = True
        return node_group

    with bpy.data.libraries.load(str(asset_path), link=True) as (source, target):
        if group_name not in source.node_groups:
            raise RuntimeError(f"Node asset is missing {group_name}")
        target.node_groups = [group_name]
    linked_group = target.node_groups[0]
    node_group = bpy.data.pack_linked_ids_hierarchy(root_id=linked_group)
    if linked_group != node_group and linked_group.users == 0:
        bpy.data.node_groups.remove(linked_group)
    node_group.use_fake_user = True
    return node_group
