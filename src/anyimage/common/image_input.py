"""Prepare independent image input files and release their temporary directories."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile

import numpy as np

from .color_image import decode_color_image
from .color_space import linear_rgb_to_srgb
from .hdr_image import is_hdr_source
from ..server.media.input import limited_image_size


def _byte_pixels(rgba):
    """Quantize normalized RGBA to byte pixels in strips."""
    pixels = np.empty(rgba.shape, dtype=np.uint8)
    # Quantize in strips to avoid a second full-size float buffer.
    for top in range(0, len(rgba), 128):
        rows = slice(top, top + 128)
        values = np.clip(rgba[rows], 0, 1)
        values *= 255
        values += 0.5
        pixels[rows] = values
    return pixels


def build_recognition_rgba(image, rgba, *, tone_map):
    """Encode straight sRGB from Blender's associated scene-linear float pixels."""
    alpha_mode = image.alpha_mode
    preview = np.empty(rgba.shape, dtype=np.float32)

    def map_rows(top):
        rows = slice(top, top + 64)
        source = rgba[rows]
        if not np.isfinite(source).all():
            raise ValueError("HDR recognition requires finite RGBA values")
        alpha = source[..., 3]
        rgb = np.array(source[..., :3].transpose(2, 0, 1), dtype=np.float64, order="C")
        np.maximum(rgb, 0, out=rgb)
        divisor = 1.0 if alpha_mode in {"CHANNEL_PACKED", "NONE"} else np.where(alpha > 0, alpha, np.inf)
        if tone_map:
            # Unpremultiplying then tone mapping gives RGB / (alpha + luminance).
            luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            divisor = divisor + luminance
        rgb /= divisor
        encoded = linear_rgb_to_srgb(rgb.astype(np.float32))
        preview[rows, :, :3] = np.clip(encoded, 0, 1).transpose(1, 2, 0)
        preview[rows, :, 3] = np.clip(alpha, 0, 1)

    # Workers only touch independent NumPy rows; all Blender access stays on the caller.
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(map_rows, range(0, len(rgba), 64)))
    return preview


def prepare_ai_input(image, rgba, *, bounds=None, max_input_size=None, panorama=False):
    """Write the current crop as top-down model RGBA, with sRGB-encoded colors."""
    from PIL import Image

    hdr = is_hdr_source(image, rgba)
    if bounds is not None:
        left, top, right, bottom = bounds
        rgba = rgba[top:bottom, left:right]
    size = rgba.shape[1::-1]
    if max_input_size is not None:
        size = limited_image_size(size, max_input_size)
    if panorama:
        height = max(1, size[0] // 2)
        size = (2 * height, height)
    space = image.colorspace_settings
    byte_input = not image.is_float and (space.name == "sRGB" or space.is_data)
    if image.is_float and space.is_data:
        if not np.isfinite(rgba).all():
            raise ValueError("AI input requires finite RGBA values")
        rgba = np.clip(rgba, 0, 1)
    elif image.is_float:
        rgba = build_recognition_rgba(image, rgba, tone_map=hdr)
    elif not byte_input:
        if space.name == "Linear Rec.709":
            rgba = rgba.copy()
        else:
            rgba = decode_color_image(image, space.name, rgba)
        rgba[..., :3] = np.clip(linear_rgb_to_srgb(rgba[..., :3]), 0, 1)
    if size != rgba.shape[1::-1]:
        alpha_filter = Image.Resampling.BOX if panorama else Image.Resampling.NEAREST
        rgba = np.stack([
            Image.fromarray(channel).resize(size, alpha_filter if index == 3 else Image.Resampling.LANCZOS)
            for index, channel in enumerate(rgba.transpose(2, 0, 1))
        ], axis=-1)
        np.clip(rgba, 0, 1, out=rgba)
    elif byte_input:
        rgba = _byte_pixels(rgba)
    if image.alpha_mode == "NONE":
        rgba[..., 3] = 255 if rgba.dtype == np.uint8 else 1
    path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / "input.npy"
    try:
        np.save(path, np.ascontiguousarray(rgba), allow_pickle=False)
    except BaseException:
        cleanup_image_input(path)
        raise
    return path


def cleanup_image_input(path):
    """Remove a prepared input and its temporary container."""
    if not path:
        return
    path = Path(path)
    directory = path.parent.resolve()
    if (directory.parent != Path(tempfile.gettempdir()).resolve()
            or not directory.name.startswith("anyimage-input-")):
        return
    try:
        path.unlink(missing_ok=True)
        (directory / "color.png").unlink(missing_ok=True)
        (directory / "color.exr").unlink(missing_ok=True)
        directory.rmdir()
    except OSError:
        pass
