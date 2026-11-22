"""Prepare independent image input files and release their temporary directories."""

from pathlib import Path
import tempfile

from .color_image import save_color_png


def prepare_input_png(rgba, *, color_space="sRGB"):
    """Encode top-down RGBA as a temporary PNG for an image job."""
    path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / "input.png"
    try:
        save_color_png(rgba, path, color_space, as_srgb=True)
    except Exception:
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
        directory.rmdir()
    except OSError:
        pass
