"""Cutout Shape identifiers shared by runtime and node-asset tools."""

BALLOON_ATTRIBUTE_NAME = "o_balloon"
NORMAL_REDUCTION_ATTRIBUTE_NAME = "o_normal_reduction"
CUTOUT_NODE_GROUP_NAMES = {
    "FLAT": "O Image Cutout",
    "SOLID": "O Image Cutout",
    "DEPTH_SYMMETRY": "O Image Cutout Symmetry",
    "DEPTH_SOLID": "O Image Depth Cutout",
}
CUTOUT_SHAPE_LABELS = {
    "FLAT": "Flat",
    "SOLID": "Solid",
    "DEPTH_SYMMETRY": "Depth Symmetry",
    "DEPTH_SOLID": "Depth Solid",
}
CUTOUT_SHAPES = frozenset(CUTOUT_NODE_GROUP_NAMES)
DEPTH_CUTOUT_SHAPES = frozenset({"DEPTH_SYMMETRY", "DEPTH_SOLID"})
