"""Build, arrange, and save the bundled node library."""
from pathlib import Path

import bpy

from .arrangement.arrange import arrange_nodes
from nodes.groups.image_plane import build_image_plane_group
from nodes.groups.image_depth_plane import build_image_depth_plane_group
from nodes.groups.image_relief_plane import build_image_relief_plane_group
from nodes.groups.image_cutout import build_image_cutout_group
from nodes.groups.image_depth_cutout import build_image_depth_cutout_group
from nodes.groups.image_cutout_symmetry import build_image_cutout_symmetry_group
from nodes.groups.image_layer import build_image_layer_group
from nodes.groups.image_depth_layer import build_image_depth_layer_group
from nodes.groups.shadeless import build_shadeless_group
from nodes.groups.image_depth_panorama import build_image_depth_panorama_group


OUTPUT_PATH = Path(__file__).resolve().parents[2] / "src/anyimage/assets/O_AnyImage.blend"


def build_node_groups():
    """Build each asset once in dependency order."""
    image_plane = build_image_plane_group()
    return [
        build_image_depth_panorama_group(),
        image_plane,
        build_image_depth_plane_group(image_plane),
        build_image_relief_plane_group(image_plane),
        build_image_cutout_group(),
        build_image_depth_cutout_group(),
        build_image_cutout_symmetry_group(),
        build_image_layer_group(),
        build_image_depth_layer_group(),
        build_shadeless_group(),
    ]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    for node_group in build_node_groups():
        arrange_nodes(node_group)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_PATH), check_existing=False)


if __name__ == "__main__":
    main()
