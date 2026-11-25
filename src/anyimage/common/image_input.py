"""Prepare independent image input files and release their temporary directories."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile

import numpy as np

from .image import byte_pixels
from .color_space import linear_rgb_to_srgb
from .hdr_image import is_hdr_source, source_encoded_rgba
from ..server.media.input import limited_image_size


def build_hdr_recognition_rgba(rgba, alpha_mode):
    """Compress HDR highlights for model recognition using straight RGB."""
    preview = np.empty(rgba.shape, dtype=np.float32)

    def map_rows(top):
        rows = slice(top, top + 64)
        source = rgba[rows]
        alpha = source[..., 3]
        rgb = np.array(source[..., :3].transpose(2, 0, 1), dtype=np.float64, order="C")
        np.maximum(rgb, 0, out=rgb)
        if alpha_mode in {"PREMUL", "STRAIGHT"}:
            rgb[:, alpha == 0] = 0
        luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        rgb /= 1 + luminance
        encoded = linear_rgb_to_srgb(rgb.astype(np.float32))
        preview[rows, :, :3] = np.clip(encoded, 0, 1).transpose(1, 2, 0)
        preview[rows, :, 3] = np.clip(alpha, 0, 1)

    # Workers only touch independent NumPy rows; all Blender access stays on the caller.
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(map_rows, range(0, len(rgba), 64)))
    return preview


def prepare_ai_input(image, rgba, *, bounds=None, max_input_size=None, panorama=False, source_rgba=None):
    """Write the current pixel buffer, mapping HDR only for model recognition."""
    from PIL import Image

    hdr = is_hdr_source(image, rgba)
    if image.is_float:
        rgba = source_encoded_rgba(image, rgba) if source_rgba is None else source_rgba
    if bounds is not None:
        left, top, right, bottom = bounds
        rgba = rgba[top:bottom, left:right]
    size = rgba.shape[1::-1]
    if max_input_size is not None:
        size = limited_image_size(size, max_input_size)
    if panorama:
        height = max(1, size[0] // 2)
        size = (2 * height, height)
    if image.is_float:
        if not np.isfinite(rgba).all():
            raise ValueError("AI input requires finite RGBA values")
        if hdr and not image.colorspace_settings.is_data:
            rgba = build_hdr_recognition_rgba(rgba, image.alpha_mode)
        rgba = np.clip(rgba, 0, 1)
    if size != rgba.shape[1::-1]:
        alpha_filter = Image.Resampling.BOX if panorama else Image.Resampling.NEAREST
        rgba = np.stack([
            Image.fromarray(channel).resize(size, alpha_filter if index == 3 else Image.Resampling.LANCZOS)
            for index, channel in enumerate(rgba.transpose(2, 0, 1))
        ], axis=-1)
        np.clip(rgba, 0, 1, out=rgba)
    elif not image.is_float:
        rgba = byte_pixels(rgba)
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
