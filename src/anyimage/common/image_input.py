"""Prepare independent image input files and release their temporary directories."""

from contextlib import contextmanager
from pathlib import Path
import tempfile

from .color_image import save_color_png
from .hdr_image import build_recognition_rgba
from ..server.media.resolution import DEFAULT_MAX_AI_INPUT_SIZE, limited_image_size


def _save_srgb_png(rgba, path):
    """Write straight sRGB pixels without creating a temporary Blender image."""
    import numpy as np
    from PIL import Image

    pixels = np.empty(rgba.shape, dtype=np.uint8)
    # Quantize in strips to avoid a second full-size float buffer.
    for top in range(0, len(rgba), 128):
        rows = slice(top, top + 128)
        values = np.clip(rgba[rows], 0, 1)
        values *= 255
        values += 0.5
        pixels[rows] = values
    Image.fromarray(pixels).save(path, compress_level=1)


@contextmanager
def _input_file(name):
    path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / name
    try:
        yield path
    except BaseException:
        cleanup_image_input(path)
        raise


def prepare_input_png(rgba, *, color_space="sRGB"):
    """Encode top-down RGBA as a temporary PNG for an image job."""
    with _input_file("input.png") as path:
        if color_space == "sRGB":
            _save_srgb_png(rgba, path)
        else:
            save_color_png(rgba, path, color_space, as_srgb=True)
    return path


def prepare_moge_input(image, rgba, *, max_input_size=DEFAULT_MAX_AI_INPUT_SIZE, panorama=False):
    """Write the current crop as top-down sRGB float32 RGBA for MoGe."""
    import numpy as np
    from PIL import Image

    size = limited_image_size(rgba.shape[1::-1], max_input_size)
    if panorama:
        height = size[0] // 2
        size = (2 * height, height)
    if image.is_float:
        rgba = build_recognition_rgba(image, rgba)
    if size != rgba.shape[1::-1]:
        alpha_filter = Image.Resampling.BOX if panorama else Image.Resampling.NEAREST
        rgba = np.stack([
            Image.fromarray(channel).resize(size, alpha_filter if index == 3 else Image.Resampling.LANCZOS)
            for index, channel in enumerate(rgba.transpose(2, 0, 1))
        ], axis=-1)
        np.clip(rgba, 0, 1, out=rgba)
    with _input_file("input.npy") as path:
        np.save(path, np.ascontiguousarray(rgba, dtype=np.float32), allow_pickle=False)
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
        directory.rmdir()
    except OSError:
        pass
