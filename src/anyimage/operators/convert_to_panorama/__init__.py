"""Image Empty panorama conversion operators."""

from .operators import ConvertToPanorama, GeneratePanorama

CLASSES = (GeneratePanorama, ConvertToPanorama)
__all__ = ("ConvertToPanorama", "GeneratePanorama", "CLASSES")
