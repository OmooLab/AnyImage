"""Shared assertions and asset selection for node tests."""
from nodes.O_AnyImage.O_AnyImage.geometry.o_cutout import OCutout
from nodes.O_AnyImage.O_AnyImage.geometry.o_depth_cutout import ODepthCutout
from nodes.O_AnyImage.O_AnyImage.geometry.o_cutout_symmetry import OCutoutSymmetry

CUTOUT_BUILDERS = {
    "FLAT": OCutout.create_group,
    "SOLID": OCutout.create_group,
    "DEPTH_SOLID": ODepthCutout.create_group,
    "DEPTH_SYMMETRY": OCutoutSymmetry.create_group,
}
