"""Shared assertions and asset selection for node tests."""
from nodes.O_AnyImage.O_AnyImage.geometry.o_image_cutout import OImageCutout
from nodes.O_AnyImage.O_AnyImage.geometry.o_image_depth_cutout import OImageDepthCutout
from nodes.O_AnyImage.O_AnyImage.geometry.o_image_cutout_symmetry import OImageCutoutSymmetry

CUTOUT_BUILDERS = {
    "FLAT": OImageCutout.create_group,
    "SOLID": OImageCutout.create_group,
    "DEPTH_SOLID": OImageDepthCutout.create_group,
    "DEPTH_SYMMETRY": OImageCutoutSymmetry.create_group,
}

ROTATION_ATTRIBUTE = "o_depth_rotation"
FACE_ATTRIBUTE = "o_depth_face"
AXIS_ATTRIBUTE = "o_depth_axis"
