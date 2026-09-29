"""Prepare and refresh the selected Blender color references."""

from typing import NamedTuple

import bpy
import numpy as np

from .color_match import prepare_color_reference
from .color_palette import extract_reference_palette
from .color_space import image_rgba_to_linear
from .image import image_rgba, is_color_reference_candidate


class PreparedReference(NamedTuple):
    image: object
    rgba: np.ndarray
    metadata: tuple
    transfer: object
    colors: np.ndarray
    weights: np.ndarray


_references = {}


def _metadata(image):
    return (tuple(image.size), image.source, image.filepath, image.is_dirty,
            image.colorspace_settings.name, image.alpha_mode)


def get_color_reference(image, *, refresh=False):
    """Reuse prepared data, optionally checking the current pixel buffer."""
    key = image.as_pointer()
    if not is_color_reference_candidate(image):
        _references.pop(key, None)
        raise ValueError("The color reference is no longer available")
    cached = _references.get(key)
    metadata = _metadata(image)
    if cached is not None and cached.image == image and cached.metadata == metadata and not refresh:
        return cached
    _references.pop(key, None)
    rgba = image_rgba(image)
    if cached is not None and cached.image == image and cached.metadata == metadata and np.array_equal(cached.rgba, rgba):
        _references[key] = cached
        return cached
    linear = image_rgba_to_linear(image, rgba)
    transfer = prepare_color_reference(linear)
    colors, weights = extract_reference_palette(linear)
    cached = PreparedReference(image, rgba, metadata, transfer, colors, weights)
    _references[key] = cached
    return cached


def clear_color_references(*_args):
    """Release snapshots after loading, undoing or disabling the add-on."""
    _references.clear()


def refresh_color_references():
    """Detect pixel edits outside Match; Image.update has no reliable notification."""
    from ..properties import update_color_reference_palette

    active = {}
    for scene in bpy.data.scenes:
        settings = getattr(scene, "anyimage_settings", None)
        reference = getattr(settings, "color_reference", None)
        if reference is None:
            continue
        key = reference.as_pointer()
        if key not in active:
            active[key] = (reference, [])
        active[key][1].append(settings)
    for key, (reference, settings_group) in active.items():
        previous = _references.get(key)
        try:
            if not is_color_reference_candidate(reference):
                raise ValueError("The color reference is no longer available")
            current = get_color_reference(reference, refresh=True)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            _references.pop(key, None)
            current = None
        if current is not previous:
            for settings in settings_group:
                update_color_reference_palette(settings, None, refresh=False)
    for key in set(_references) - set(active):
        _references.pop(key, None)
    return 0.5


def register():
    clear_color_references._bpy_persistent = True
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if clear_color_references not in handlers:
            handlers.append(clear_color_references)
    if not bpy.app.timers.is_registered(refresh_color_references):
        bpy.app.timers.register(refresh_color_references, first_interval=0.5, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(refresh_color_references):
        bpy.app.timers.unregister(refresh_color_references)
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
        if clear_color_references in handlers:
            handlers.remove(clear_color_references)
    clear_color_references()
