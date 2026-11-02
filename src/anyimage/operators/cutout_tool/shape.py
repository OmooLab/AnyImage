"""Cutout Shape identifiers shared by runtime and node-asset tools."""

BALLOON_ATTRIBUTE_NAME = "o_balloon"
NORMAL_REDUCTION_ATTRIBUTE_NAME = "o_normal_reduction"
IMAGE_REGION_ATTRIBUTE_NAME = "o_image_region"
CUTOUT_NODE_GROUP_NAMES = {
    "FLAT": "O Cutout",
    "SOLID": "O Cutout",
    "DEPTH_SYMMETRY": "O Cutout Symmetry",
    "DEPTH_SOLID": "O Depth Cutout",
}
CUTOUT_SHAPE_LABELS = {
    "FLAT": "Flat",
    "SOLID": "Solid",
    "DEPTH_SYMMETRY": "Depth Symmetry",
    "DEPTH_SOLID": "Depth Solid",
}

DEPTH_CUTOUT_SHAPES = frozenset({"DEPTH_SYMMETRY", "DEPTH_SOLID"})
