"""Prepare and refresh the selected Blender color references."""

from typing import NamedTuple

import bpy
import numpy as np

from .color_match import prepare_color_reference, resize_rgba_proxy
from .color_palette import extract_reference_palette
from .color_space import image_rgba_to_linear, linear_rgb_to_srgb
from .image import image_rgba, is_color_reference_candidate


class PreparedReference(NamedTuple):
    image: object
    rgba: np.ndarray
    metadata: tuple
    transfer: object
    colors: np.ndarray
    weights: np.ndarray


_references = {}
_previews = None


def color_reference_preview_icon(image):
    """Return a prepared preview detached from Image dependency graph updates."""
    key = str(image.as_pointer())
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


def refresh_edited_color_reference(image):
    """Refresh previously prepared references after a known content edit."""
    key = image.as_pointer()
    prepared = key in _references or (_previews is not None and str(key) in _previews)
    invalidate_color_reference(image)
    if not prepared:
        return
    from ..properties import update_color_reference_palette

    settings_group = [
        scene.anyimage_settings
        for scene in bpy.data.scenes
        if getattr(getattr(scene, "anyimage_settings", None), "color_reference", None) == image
    ]
    if settings_group:
        for settings in settings_group:
            update_color_reference_palette(settings, None, refresh=False)
    else:
        try:
            get_color_reference(image)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            pass


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
    if cached is not None and cached.image == image and cached.metadata == metadata and np.array_equal(cached.rgba, rgba):
        _references[key] = cached
        return cached
    invalidate_color_reference(image)
    linear = image_rgba_to_linear(image, rgba)
    colors, weights = extract_reference_palette(linear)
    transfer = prepare_color_reference(linear, colors, weights)
    _prepare_reference_preview(image, linear)
    cached = PreparedReference(image, rgba, metadata, transfer, colors, weights)
    _references[key] = cached
    return cached


def clear_color_references(*_args):
    """Release snapshots after loading, undoing or disabling the add-on."""
    _references.clear()
    if _previews is not None:
        _previews.clear()
    from ..properties import invalidate_color_reference_items

    invalidate_color_reference_items()


def restore_color_references(*_args):
    """Rebuild selected references from restored Blender data after Undo or load."""
    from ..properties import update_color_reference_palette

    clear_color_references()
    for scene in bpy.data.scenes:
        settings = getattr(scene, "anyimage_settings", None)
        if settings is not None and settings.color_reference is not None:
            update_color_reference_palette(settings, None, refresh=False)


def register():
    restore_color_references._bpy_persistent = True
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if restore_color_references not in handlers:
            handlers.append(restore_color_references)


def unregister():
    global _previews
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if restore_color_references in handlers:
            handlers.remove(restore_color_references)
    clear_color_references()
    if _previews is not None:
        from bpy.utils import previews

        previews.remove(_previews)
        _previews = None
