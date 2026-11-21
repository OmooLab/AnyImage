"""Pack clipboard images and reuse unchanged cached images."""

import hashlib
import os
import tempfile

import bpy

from ...common.image import CLIPBOARD_HASH_PROPERTY, image_pixels


CLIPBOARD_CONTENT_PROPERTY = "anyimage_clipboard_content_sha256"


def acquire_packed_image(image_data, suffix):
    image_hash = hashlib.sha256(image_data).hexdigest()
    existing_image = _find_packed_clipboard_image(image_hash)
    if existing_image is not None:
        return existing_image, True

    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix="blender-clipboard-",
        suffix=suffix,
    )
    image = None
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(image_data)
        image = bpy.data.images.load(temporary_path, check_existing=False)
        image.name = "Clipboard"
        image.pack()
        image[CLIPBOARD_HASH_PROPERTY] = image_hash
        image[CLIPBOARD_CONTENT_PROPERTY] = _clipboard_content_hash(image)
        return image, False
    except Exception:
        if image is not None:
            bpy.data.images.remove(image)
        raise
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _find_packed_clipboard_image(image_hash):
    for image in bpy.data.images:
        if image.get(CLIPBOARD_HASH_PROPERTY) != image_hash:
            continue
        if not image.packed_files:
            continue
        baseline = image.get(CLIPBOARD_CONTENT_PROPERTY)
        if not baseline:
            continue
        try:
            if _clipboard_content_hash(image) == baseline:
                return image
        except (RuntimeError, ValueError, ReferenceError, OSError):
            continue
    return None


def _clipboard_content_hash(image):
    """Fingerprint current pixels and interpretation without changing the image."""
    digest = hashlib.sha256()
    digest.update(repr((tuple(image.size), image.colorspace_settings.name, image.alpha_mode)).encode())
    digest.update(image_pixels(image))
    return digest.hexdigest()
