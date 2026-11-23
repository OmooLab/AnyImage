"""Size AI inputs, read Blender RGBA snapshots and prepare model tensors."""


DEFAULT_MAX_AI_INPUT_SIZE = 2048
MIN_MAX_AI_INPUT_SIZE = 256
MAX_MAX_AI_INPUT_SIZE = 8192


def normalized_max_input_size(value):
    size = int(value)
    if size < 1 or size > MAX_MAX_AI_INPUT_SIZE:
        raise ValueError(
            f"Maximum AI Input Size must be between 1 and "
            f"{MAX_MAX_AI_INPUT_SIZE} pixels"
        )
    return size


def limited_image_size(image_size, max_input_size=DEFAULT_MAX_AI_INPUT_SIZE):
    width, height = (int(value) for value in image_size)
    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be positive")
    maximum = normalized_max_input_size(max_input_size)
    longest = max(width, height)
    if longest <= maximum:
        return width, height
    scale = maximum / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


def limit_image(image, max_input_size=DEFAULT_MAX_AI_INPUT_SIZE):
    from PIL import Image

    size = limited_image_size(image.size, max_input_size)
    if size == image.size:
        return image
    return image.resize(size, Image.Resampling.LANCZOS)


def load_ai_input(path, *, as_bytes=False):
    """Read normalized float RGBA or byte RGBA for Pillow-based model adapters."""
    import numpy as np

    try:
        rgba = np.load(path, allow_pickle=False)
    except (OSError, ValueError, EOFError) as error:
        raise ValueError("Unable to read the AI image input") from error
    if not isinstance(rgba, np.ndarray):
        rgba.close()
        raise ValueError("Expected a single RGBA array")
    if rgba.ndim != 3 or rgba.shape[2] != 4 or not rgba.size:
        raise ValueError("AI input must be a nonempty RGBA image")
    if rgba.dtype == np.uint8:
        if as_bytes:
            return rgba
        # Match Blender's byte-to-float conversion.
        return rgba.astype(np.float32) * np.float32(1 / 255)
    if rgba.dtype != np.float32 or not (rgba.min() >= 0 and rgba.max() <= 1):
        raise ValueError("AI input must contain uint8 or normalized float32 values")
    if as_bytes:
        rgba *= 255
        rgba += 0.5
        return rgba.astype(np.uint8)
    return rgba


def imagenet_rgb_tensor(image):
    """Normalize RGB with ImageNet statistics and return a contiguous NCHW tensor."""
    import numpy as np

    array = np.asarray(image, dtype=np.float32) / 255.0
    array -= np.array((0.485, 0.456, 0.406), dtype=np.float32)
    array /= np.array((0.229, 0.224, 0.225), dtype=np.float32)
    return np.ascontiguousarray(array.transpose(2, 0, 1)[None])
