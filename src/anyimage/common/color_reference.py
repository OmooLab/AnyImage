"""Prepare and refresh the selected Blender color references."""

import hashlib
from typing import NamedTuple

import bpy
import numpy as np

from .color_match import prepare_color_reference, resize_rgba_proxy
from .color_palette import extract_reference_palette
from .color_space import image_rgba_to_linear, linear_rgb_to_srgb
from .image import image_rgba, is_color_reference_candidate


class PreparedReference(NamedTuple):
    image: object
    content_digest: bytes
    metadata: tuple
    transfer: object
    colors: np.ndarray
    weights: np.ndarray


_references = {}
_retained = {}
_previews = None


def color_reference_preview_icon(image, *, prepare=False):
    """Return a prepared preview detached from Image dependency graph updates."""
    key = str(image.as_pointer())
    if prepare and (_previews is None or key not in _previews):
        _prepare_reference_preview(image, image_rgba_to_linear(image, image_rgba(image)))
    if _previews is not None and key in _previews:
        return _previews[key].icon_id
    return 0


def _prepare_reference_preview(image, linear):
    from bpy.utils import previews

    global _previews
    if _previews is None:
        _previews = previews.new()
    key = str(image.as_pointer())
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
    _references.pop(image.as_pointer(), None)
    key = str(image.as_pointer())
    if _previews is not None and key in _previews:
        del _previews[key]


def release_unused_color_references(images):
    """Keep selected reference data and gallery candidate previews."""
    keys = {image.as_pointer() for image in images if image is not None} | set(_retained)
    for key in tuple(_references):
        if key not in keys:
            _references.pop(key)
    preview_keys = {str(key) for key in keys} | {
        str(image.as_pointer()) for image in bpy.data.images if is_color_reference_candidate(image)
    }
    if _previews is not None:
        for key in tuple(_previews):
            if key not in preview_keys:
                del _previews[key]


def retain_color_reference(image):
    """Keep the selected reference resources for one active interaction."""
    key = image.as_pointer()
    _retained[key] = _retained.get(key, 0) + 1
    return key


def release_color_reference(key):
    """End one interaction's resource ownership."""
    count = _retained.get(key, 0)
    if count <= 1:
        _retained.pop(key, None)
    else:
        _retained[key] = count - 1


def color_reference_digest(rgba):
    """Identify complete pixels without retaining a full-size snapshot."""
    digest = hashlib.blake2b(digest_size=32)
    for row in rgba:
        digest.update(memoryview(np.ascontiguousarray(row)))
    return digest.digest()


def _metadata(image):
    return (tuple(image.size), image.source, image.filepath, image.is_dirty,
            image.colorspace_settings.name, image.alpha_mode)


def get_color_reference(image, *, refresh=False):
    """Reuse prepared data, optionally checking the current pixel buffer."""
    key = image.as_pointer()
    if not is_color_reference_candidate(image):
        invalidate_color_reference(image)
        raise ValueError("The color reference is no longer available")
    cached = _references.get(key)
    metadata = _metadata(image)
    if cached is not None and cached.image == image and cached.metadata == metadata and not refresh:
        return cached
    _references.pop(key, None)
    try:
        rgba = image_rgba(image)
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        invalidate_color_reference(image)
        raise
    content_digest = color_reference_digest(rgba)
    if cached is not None and cached.image == image and cached.metadata == metadata and cached.content_digest == content_digest:
        _references[key] = cached
        return cached
    invalidate_color_reference(image)
    linear = image_rgba_to_linear(image, rgba)
    colors, weights = extract_reference_palette(linear)
    transfer = prepare_color_reference(linear, colors, weights)
    _prepare_reference_preview(image, linear)
    cached = PreparedReference(image, content_digest, metadata, transfer, colors, weights)
    _references[key] = cached
    return cached


def clear_color_references():
    """Release all reference resources at a global data lifecycle boundary."""
    global _previews
    _references.clear()
    _retained.clear()
    if _previews is not None:
        from bpy.utils import previews

        previews.remove(_previews)
        _previews = None
