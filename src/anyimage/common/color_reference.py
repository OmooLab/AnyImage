"""Prepare and refresh the selected Blender color references."""

from typing import NamedTuple

import bpy
import numpy as np

from .color_match import ColorReference, prepare_color_reference, resize_rgba_proxy
from .color_space import image_rgba_to_linear, linear_rgb_to_srgb
from .image import image_rgba, image_content_handlers, pixel_digest


class PreparedReference(NamedTuple):
    image: object
    content_digest: bytes
    metadata: tuple
    transfer: ColorReference | None
    icon_id: int


_references = {}
_previews = None


def _prepare_reference_preview(key, linear):
    from bpy.utils import previews

    global _previews
    if _previews is None:
        _previews = previews.new()
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
    return preview.icon_id


def _metadata(image):
    return (tuple(image.size), image.source, image.filepath, image.is_dirty,
            image.colorspace_settings.name, image.alpha_mode)


def get_color_reference(image, *, refresh=False):
    """Reuse prepared data, optionally checking the current pixel buffer."""
    key = str(image.session_uid)
    cached = _references.get(key)
    metadata = _metadata(image)
    if cached is not None and cached.image == image and cached.metadata == metadata and not refresh:
        return cached
    rgba = image_rgba(image)
    content_digest = pixel_digest(rgba)
    if cached is not None and cached.image == image and cached.metadata == metadata and cached.content_digest == content_digest:
        return cached
    linear = image_rgba_to_linear(image, rgba)
    transfer = prepare_color_reference(linear) if np.any(linear[..., 3] > 0) else None
    icon_id = _prepare_reference_preview(key, linear)
    prepared = PreparedReference(image, content_digest, metadata, transfer, icon_id)
    _references[key] = prepared
    return prepared


def invalidate_color_reference(image):
    key = str(image.session_uid)
    _references.pop(key, None)
    if _previews is not None and key in _previews:
        del _previews[key]


def release_unused_references(_settings, _context):
    selected = {scene.anyimage_settings.color_reference for scene in bpy.data.scenes}
    keep = {str(image.session_uid) for image in selected if image is not None}
    for key in _references.keys() - keep:
        del _references[key]
        if _previews is not None and key in _previews:
            del _previews[key]


def clear_color_references(*_args):
    global _previews
    _references.clear()
    if _previews is not None:
        from bpy.utils import previews

        previews.remove(_previews)
        _previews = None


def register_color_references():
    clear_color_references._bpy_persistent = True
    for handlers in (
        bpy.app.handlers.load_post,
        bpy.app.handlers.undo_post,
        bpy.app.handlers.redo_post,
    ):
        if clear_color_references not in handlers:
            handlers.append(clear_color_references)
    if invalidate_color_reference not in image_content_handlers:
        image_content_handlers.append(invalidate_color_reference)


def unregister_color_references():
    for handlers in (
        bpy.app.handlers.load_post,
        bpy.app.handlers.undo_post,
        bpy.app.handlers.redo_post,
    ):
        if clear_color_references in handlers:
            handlers.remove(clear_color_references)
    if invalidate_color_reference in image_content_handlers:
        image_content_handlers.remove(invalidate_color_reference)
    clear_color_references()
