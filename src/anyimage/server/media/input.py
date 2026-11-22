from contextlib import contextmanager
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@contextmanager
def open_image(path):
    """Validate and decode a still image before handing it to a job."""
    from PIL import Image

    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f"Source image file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise RuntimeError(
            f"Unsupported input format: {suffix or '(no extension)'}. "
            f"Supported images: {', '.join(sorted(IMAGE_SUFFIXES))}."
        )

    opened = None
    try:
        try:
            opened = Image.open(path)
            opened.load()
            if getattr(opened, "n_frames", 1) != 1:
                raise RuntimeError("Only still images are supported")
        except (OSError, ValueError, SyntaxError) as error:
            raise RuntimeError(f"Unable to read image: {path}") from error
        yield opened
    finally:
        if opened is not None:
            opened.close()
