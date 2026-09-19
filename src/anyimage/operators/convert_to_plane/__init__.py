"""Rectangular Plane and Depth Plane conversion operators."""

from .operators import (
    ConvertToDepthPlane,
    ConvertToReliefPlane,
    ConvertToPlane,
    GenerateDepthPlane,
)

CLASSES = (GenerateDepthPlane, ConvertToPlane, ConvertToDepthPlane, ConvertToReliefPlane)

__all__ = (
    "CLASSES",
    "ConvertToDepthPlane",
    "ConvertToReliefPlane",
    "ConvertToPlane",
    "GenerateDepthPlane",
)
