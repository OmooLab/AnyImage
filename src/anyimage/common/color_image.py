"""Prepare, interpret and normalize material color images."""

import tempfile
from contextlib import contextmanager
from pathlib import Path

import bpy

from .image import (
    COLOR_NORMALIZED_PROPERTY,
    ImageFormat,
    image_base_name,
    image_rgba,
    is_animated_image,
    image_pixels,
)


VIEW_TRANSFORM_COLOR_SPACES = (
    ("ACES 1.3", "ACES 1.3 sRGB"),
    ("ACES 2.0", "ACES 2.0 sRGB"),
    ("AgX", "AgX Base sRGB"),
    ("Filmic", "Filmic sRGB"),
    ("Khronos PBR Neutral", "Khronos PBR Neutral sRGB"),
)


def color_alpha_mode(color_space):
    """Pair inverse view color spaces with straight alpha."""
    return "STRAIGHT" if color_space in dict(VIEW_TRANSFORM_COLOR_SPACES).values() else "PREMUL"


def material_color_space_name(scene):
    view_settings = getattr(scene, "view_settings", None)
    view_transform = getattr(view_settings, "view_transform", "")
    normalized = str(view_transform).strip().casefold()
    for view_name, color_space in VIEW_TRANSFORM_COLOR_SPACES:
        if normalized.startswith(view_name.casefold()):
            return color_space
    return "sRGB"


def configure_material_color_image(image, scene=None):
    """Preserve HDR and interpret byte colors through the inverse view transform."""
    if getattr(image, "is_float", False):
        return image
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    preferred = material_color_space_name(scene)
    pixels = (
        image_pixels(image)
        if getattr(image, "source", None) == "GENERATED"
        or getattr(image, "is_dirty", False)
        else None
    )
    settings = image.colorspace_settings
    original_space = settings.name
    original_alpha = image.alpha_mode
    try:
        for color_space in dict.fromkeys((preferred, "sRGB")):
            try:
                settings.name = color_space
            except (TypeError, ValueError):
                continue
            if settings.name == color_space:
                break
        else:
            raise RuntimeError("Unable to configure the material color space")
        image.alpha_mode = color_alpha_mode(settings.name)
        if pixels is not None:
            image.pixels.foreach_set(pixels)
            image.update()
        if COLOR_NORMALIZED_PROPERTY in image:
            del image[COLOR_NORMALIZED_PROPERTY]
    except Exception:
        settings.name = original_space
        image.alpha_mode = original_alpha
        if pixels is not None:
            image.pixels.foreach_set(pixels)
            image.update()
        raise
    return image


def create_normalized_color_image(image, rgba=None):
    """Build a bounded sRGB color image independently of shading preferences."""
    import numpy as np
    from .color_space import normalize_color_rgba

    if rgba is None:
        rgba = image_rgba(image)
    if not image.get(COLOR_NORMALIZED_PROPERTY) and (image.is_float or image.colorspace_settings.name != "sRGB"):
        rgba = normalize_color_rgba(decode_color_image(image, image.colorspace_settings.name, rgba))
    elif not np.isfinite(rgba).all():
        raise ValueError("Color normalization requires finite RGBA values")
    height, width = rgba.shape[:2]
    result = bpy.data.images.new(image.name, width=width, height=height, alpha=True)
    try:
        result.colorspace_settings.name = "sRGB"
        result.alpha_mode = "PREMUL"
        result.file_format = "PNG"
        result[COLOR_NORMALIZED_PROPERTY] = True
        result.pixels.foreach_set(np.flipud(np.clip(rgba, 0, 1)).ravel())
        result.update()
        return result
    except Exception:
        bpy.data.images.remove(result)
        raise


def decode_color_image(image, color_space, rgba=None):
    """Evaluate RGB through Blender color management, preserving business alpha."""
    import numpy as np

    if rgba is None:
        rgba = image_rgba(image)
    if not np.isfinite(rgba).all():
        raise ValueError("Color normalization requires finite RGBA values")
    height, width = rgba.shape[:2]
    reader = bpy.data.images.new("Color Decode", width=width, height=height, alpha=True, float_buffer=image.is_float)
    scene = decoded = None
    try:
        reader.colorspace_settings.name = color_space
        reader.alpha_mode = "STRAIGHT"
        opaque = rgba.copy()
        opaque[..., 3] = 1
        reader.pixels.foreach_set(np.flipud(opaque).ravel())
        scene = bpy.data.scenes.new("Color Decode")
        settings = scene.render.image_settings
        settings.file_format = "OPEN_EXR"
        settings.color_mode = "RGB"
        settings.color_depth = "32"
        with tempfile.TemporaryDirectory(prefix="anyimage-color-") as directory:
            path = Path(directory) / "linear.exr"
            reader.save_render(str(path), scene=scene)
            decoded = bpy.data.images.load(str(path), check_existing=False)
            linear = image_rgba(decoded)
            linear[..., 3] = rgba[..., 3]
        return linear
    finally:
        if decoded is not None:
            bpy.data.images.remove(decoded)
        if scene is not None:
            bpy.data.scenes.remove(scene)
        bpy.data.images.remove(reader)


def _material_png_colors(rgba, source_space):
    """Convert distinct source RGB values with Blender's material PNG encoder."""
    import numpy as np
    from PIL import Image

    rgb = np.rint(rgba[..., :3] * 255).astype(np.uint8)
    colors, indices = np.unique(rgb.reshape(-1, 3), axis=0, return_inverse=True)
    width = min(1024, len(colors))
    rows = (len(colors) + width - 1) // width
    swatches = np.ones((rows * width, 4), dtype=np.float32)
    swatches[:len(colors), :3] = colors / 255.0
    with tempfile.TemporaryDirectory(prefix="anyimage-color-") as directory:
        path = Path(directory) / "swatches.png"
        save_color_png(swatches.reshape(rows, width, 4), path, source_space)
        with Image.open(path) as encoded:
            palette = np.asarray(encoded.convert("RGB")).reshape(-1, 3)
    return palette[indices].reshape(rgb.shape).astype(np.float32) / 255.0


def linear_color_rgba(image, rgba=None, *, material_space=None, alpha_mode=None):
    """Read straight-alpha linear RGB while preserving the image alpha."""
    import numpy as np
    from .color_space import srgb_to_linear_rgb

    space = material_space or image.colorspace_settings.name
    mode = alpha_mode or image.alpha_mode
    rgba = image_rgba(image) if rgba is None else rgba.copy()
    if material_space is not None:
        source_space = image.colorspace_settings
        if not image.is_float and not source_space.is_data and source_space.name != "sRGB":
            rgba[..., :3] = _material_png_colors(rgba, source_space.name)
        if image.is_float and mode == "NONE":
            rgba[..., 3] = 1
    if not image.is_float and space == "sRGB":
        rgba[..., :3] = srgb_to_linear_rgb(rgba[..., :3])
    elif not (image.is_float and (space == "Linear Rec.709" or (material_space is None and image.colorspace_settings.is_data))):
        rgba = decode_color_image(image, space, rgba)
    if image.is_float and mode in {"STRAIGHT", "PREMUL"}:
        rgba[..., :3] /= np.where(rgba[..., 3:4] > 0, rgba[..., 3:4], 1)
    return rgba


def _luminance_split(values, percentile, *, logarithmic=False):
    """Separate dark and bright luminance by maximum between-class variance."""
    import numpy as np

    values = np.minimum(values, np.quantile(values, percentile))
    if logarithmic:
        values = np.log2(np.maximum(values, 1e-6))
    histogram, edges = np.histogram(values, bins=256)
    centers = (edges[:-1] + edges[1:]) / 2
    counts = np.cumsum(histogram)
    sums = np.cumsum(histogram * centers)
    variance = (sums[-1] * counts - sums * counts[-1]) ** 2 / np.maximum(
        counts * (counts[-1] - counts), 1,
    )
    split = edges[np.argmax(variance[:-1]) + 1]
    return max(float(2 ** split if logarithmic else split), 0.0001)


def estimate_highlight_threshold(image, *, panorama=False, material_image=None, rgba=None, material_space=None, alpha_mode=None):
    """Estimate highlight onset from full RGB and spatial brightness contrast."""
    import numpy as np

    if material_image is not None and material_image != image:
        material_space = material_image.colorspace_settings.name
        alpha_mode = material_image.alpha_mode
    rgba = linear_color_rgba(image, rgba, material_space=material_space, alpha_mode=alpha_mode)
    if not (rgba[..., 3] > 0.1).any() or not np.isfinite(rgba).all():
        return 1.0
    # Transparent pixels retain the original surroundings; alpha is not a weight.
    luminance = rgba[..., :3] @ np.array((.2126, .7152, .0722))
    if np.ptp(luminance) == 0:
        return 1.0
    high = _luminance_split(luminance, .99)
    bright_fraction = np.mean(luminance > high)
    height, width = luminance.shape
    if panorama:
        band = max(1, height // 3)
        reference = max(float(np.median(luminance[-band:])), .0001)
        subject = float(np.median(luminance[:band]))
        base = high
        target = _luminance_split(luminance, .95, logarithmic=True)
    else:
        rows, columns = max(1, height // 10), max(1, width // 10)
        corners = [np.median(region) for region in (
            luminance[:rows, :columns], luminance[:rows, -columns:],
            luminance[-rows:, :columns], luminance[-rows:, -columns:],
        )]
        dark, typical = np.quantile(corners, (.25, .5))
        reference = max(float(dark), .0001)
        subject = float(np.median(luminance[
            height // 4:height - height // 4, width // 4:width - width // 4,
        ]))
        base = max(high, float(typical))
        target = reference
    # Broaden emission with 5–10% bright area and 2–4x spatial contrast.
    area_weight = np.clip(20 * bright_fraction - 1, 0, 1)
    contrast_weight = np.clip(np.log2(max(subject / reference, .0001)) - 1, 0, 1)
    weight = area_weight * contrast_weight
    return float(np.exp((1 - weight) * np.log(base) + weight * np.log(target)))


def require_static_color_image(image):
    """Reject animated inputs before preparing material resources."""
    if is_animated_image(image):
        raise ValueError("Material conversion supports static images only")


def save_color_png(rgba, path, color_space):
    """Save top-down RGBA pixels with their Blender color interpretation."""
    import numpy as np

    height, width = rgba.shape[:2]
    image = bpy.data.images.new("Material Color Export", width=width, height=height, alpha=True)
    try:
        image.colorspace_settings.name = color_space
        image.alpha_mode = "STRAIGHT"
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        image.file_format = "PNG"
        image.save(filepath=str(path), save_copy=True)
        if not path.is_file():
            raise RuntimeError("Unable to export the material color image")
    finally:
        bpy.data.images.remove(image)


def create_material_color_image(source, bounds=None, rgba=None):
    """Pack the selected source pixels as a material PNG or scene-linear EXR."""
    require_static_color_image(source)
    width, height = map(int, source.size)
    if rgba is None:
        rgba = image_rgba(source)
    if rgba.shape != (height, width, 4):
        raise ValueError("The source RGBA does not match the Blender Image")
    left, top, right, bottom = (0, 0, width, height) if bounds is None else map(int, bounds)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("The material color bounds are outside the image")
    cropped = rgba[top:bottom, left:right]
    return create_crop_color_image(image_base_name(source), ImageFormat.capture(source), cropped)


def material_highlight_threshold(source, rgba, scene, *, panorama=False):
    """Evaluate the full source using the material crop's color interpretation."""
    if source.is_float:
        space = "Linear Rec.709"
        alpha = "PREMUL" if source.alpha_mode == "STRAIGHT" else source.alpha_mode
    else:
        space = material_color_space_name(scene)
        alpha = color_alpha_mode(space)
    return estimate_highlight_threshold(source, rgba=rgba, material_space=space, alpha_mode=alpha, panorama=panorama)


def write_material_color(directory, fmt, rgba):
    from .hdr_image import save_hdr_image

    if fmt.is_float:
        path = directory / "color.exr"
        save_hdr_image(rgba, path)
    else:
        path = directory / "color.png"
        save_color_png(rgba, path, fmt.color_space)
    return path


def load_material_color(path, name, fmt):
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.name = f"{name}_color{path.suffix}"
        image.colorspace_settings.name = "Linear Rec.709" if fmt.is_float else fmt.color_space
        image.alpha_mode = "PREMUL" if fmt.is_float and fmt.alpha_mode == "STRAIGHT" else fmt.alpha_mode
        if fmt.normalized:
            image[COLOR_NORMALIZED_PROPERTY] = True
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image)
        raise


def create_crop_color_image(name, fmt, cropped):
    """Pack a captured material crop without accessing its source datablock."""
    with tempfile.TemporaryDirectory(prefix="anyimage-color-") as directory:
        path = write_material_color(Path(directory), fmt, cropped)
        return load_material_color(path, name, fmt)


@contextmanager
def material_color_image(source, *, bounds=None, rgba=None):
    """Keep the packed image when the result uses it."""
    image = create_material_color_image(source, bounds, rgba)
    try:
        yield image
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise
    else:
        if image.users == 0:
            bpy.data.images.remove(image)
