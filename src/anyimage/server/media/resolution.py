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
