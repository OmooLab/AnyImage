"""Pack clipboard images and reuse unchanged cached images."""

import hashlib
from contextlib import contextmanager
from pathlib import Path
import tempfile

import bpy

from ...common.image import CLIPBOARD_HASH_PROPERTY, image_pixels


CLIPBOARD_CONTENT_PROPERTY = "anyimage_clipboard_content_sha256"


@contextmanager
def clipboard_source(image_data, suffix):
    """Keep the source file available until the pasted image is committed."""
    image_hash = hashlib.sha256(image_data).hexdigest()
    existing = _find_packed_clipboard_image(image_hash)
    if existing is not None:
        yield existing
        return
    with tempfile.TemporaryDirectory(prefix="blender-clipboard-") as directory:
        path = Path(directory) / ("clipboard" + suffix)
        path.write_bytes(image_data)
        image = bpy.data.images.load(str(path), check_existing=False)
        try:
            image.name = "Clipboard"
            image[CLIPBOARD_HASH_PROPERTY] = image_hash
            image[CLIPBOARD_CONTENT_PROPERTY] = _clipboard_content_hash(image)
            yield image
        finally:
            if image.users == 0:
                bpy.data.images.remove(image)


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
