"""Prepare and refresh the selected Blender color references."""

from typing import NamedTuple

import bpy
import numpy as np

from .color_match import ColorReference, prepare_color_reference, resize_rgba_proxy
from .color_space import image_rgba_to_linear, linear_rgb_to_srgb
from .image import image_rgba, is_color_reference_candidate, pixel_digest


class PreparedReference(NamedTuple):
    image: object
    content_digest: bytes
    metadata: tuple
    transfer: ColorReference


_references = {}
_previews = None


def color_reference_preview_icon(image):
    """Return the gallery icon, preparing it on first use."""
    key = str(image.session_uid)
    if _previews is None or key not in _previews:
        _prepare_reference_preview(image, image_rgba_to_linear(image, image_rgba(image)))
    return _previews[key].icon_id


def _prepare_reference_preview(image, linear):
    from bpy.utils import previews

    global _previews
    if _previews is None:
        _previews = previews.new()
    key = str(image.session_uid)
    preview = _previews[key] if key in _previews else _previews.new(key)
    premultiplied = linear.copy()
    premultiplied[..., 3] = np.clip(premultiplied[..., 3], 0.0, 1.0)
    premultiplied[..., :3] *= premultiplied[..., 3:4]
    for prefix, maximum in (("image", 128), ("icon", 32)):
        rgba = resize_rgba_proxy(premultiplied, max_size=maximum)
        np.divide(rgba[..., :3], rgba[..., 3:4], out=rgba[..., :3], where=rgba[..., 3:4] > 1e-8)
        rgba[..., :3] = np.clip(linear_rgb_to_srgb(rgba[..., :3]), 0.0, 1.0)
        rgba[..., :3] *= rgba[..., 3:4]
        setattr(preview, f"{prefix}_size", (rgba.shape[1], rgba.shape[0]))
        setattr(preview, f"{prefix}_pixels_float", np.flipud(rgba).ravel())


def invalidate_color_reference(image):
    """Release derived reference data after a known image content replacement."""
    key = str(image.session_uid)
    _references.pop(key, None)
    if _previews is not None and key in _previews:
        del _previews[key]


def release_unused_color_references(candidates):
    """Keep selected reference data and gallery candidate previews."""
    selected = set()
    for scene in bpy.data.scenes:
        settings = getattr(scene, "anyimage_settings", None)
        if settings is not None and settings.color_reference is not None:
            selected.add(str(settings.color_reference.session_uid))
    for key in _references.keys() - selected:
        del _references[key]
    if _previews is not None:
        keep = selected.union(str(image.session_uid) for image in candidates)
        for key in _previews.keys() - keep:
            del _previews[key]


def _metadata(image):
    return (tuple(image.size), image.source, image.filepath, image.is_dirty,
            image.colorspace_settings.name, image.alpha_mode)


def get_color_reference(image, *, refresh=False):
    """Reuse prepared data, optionally checking the current pixel buffer."""
    key = str(image.session_uid)
    if not is_color_reference_candidate(image):
        invalidate_color_reference(image)
        raise ValueError("The color reference is no longer available")
    cached = _references.get(key)
    metadata = _metadata(image)
    if cached is not None and cached.image == image and cached.metadata == metadata and not refresh:
        return cached
    try:
        rgba = image_rgba(image)
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        invalidate_color_reference(image)
        raise
    content_digest = pixel_digest(rgba)
    if cached is not None and cached.image == image and cached.metadata == metadata and cached.content_digest == content_digest:
        return cached
    invalidate_color_reference(image)
    linear = image_rgba_to_linear(image, rgba)
    transfer = prepare_color_reference(linear)
    _prepare_reference_preview(image, linear)
    cached = PreparedReference(image, content_digest, metadata, transfer)
    _references[key] = cached
    return cached


def clear_color_references():
    """Release all reference resources at a global data lifecycle boundary."""
    global _previews
    _references.clear()
    if _previews is not None:
        from bpy.utils import previews

        previews.remove(_previews)
        _previews = None
