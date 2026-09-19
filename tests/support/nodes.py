"""Shared assertions and asset selection for node tests."""
from nodes.groups.image_cutout import build_image_cutout_group
from nodes.groups.image_depth_cutout import build_image_depth_cutout_group
from nodes.groups.image_cutout_symmetry import build_image_cutout_symmetry_group

CUTOUT_BUILDERS = {
    "FLAT": build_image_cutout_group,
    "SOLID": build_image_cutout_group,
    "DEPTH_SOLID": build_image_depth_cutout_group,
    "DEPTH_SYMMETRY": build_image_cutout_symmetry_group,
}
