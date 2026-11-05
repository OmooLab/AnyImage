"""Prepare, interpret and normalize material color images."""

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import bpy

from .image import (
    COLOR_NORMALIZED_PROPERTY,
    image_base_name,
    image_rgba,
    is_animated_image,
    image_pixels,
)
from .image_input import cleanup_image_input


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


def create_normalized_color_image(image):
    """Build a bounded sRGB color image independently of shading preferences."""
    import numpy as np
    from .color_space import normalize_color_rgba

    rgba = image_rgba(image)
    if not np.isfinite(rgba).all():
        raise ValueError("Color normalization requires finite RGBA values")
    if not image.get(COLOR_NORMALIZED_PROPERTY) and (image.is_float or image.colorspace_settings.name != "sRGB"):
        rgba = normalize_color_rgba(decode_color_image(image, image.colorspace_settings.name))
    result = bpy.data.images.new(image.name, width=image.size[0], height=image.size[1], alpha=True)
    try:
        result.colorspace_settings.name = "sRGB"
        result.alpha_mode = "PREMUL"
        result.file_format = "PNG"
        result[COLOR_NORMALIZED_PROPERTY] = True
        result.pixels.foreach_set(np.flipud(np.clip(rgba, 0, 1)).ravel())
        result.update()
        result.pack()
        return result
    except Exception:
        bpy.data.images.remove(result)
        raise


def decode_color_image(image, color_space):
    """Evaluate RGB through Blender color management, preserving business alpha."""
    import numpy as np

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
            rgba[..., :3] = image_rgba(decoded)[..., :3]
        return rgba
    finally:
        if decoded is not None:
            bpy.data.images.remove(decoded)
        if scene is not None:
            bpy.data.scenes.remove(scene)
        bpy.data.images.remove(reader)


def linear_color_rgba(image):
    """Read straight-alpha linear RGB while preserving the image alpha."""
    import numpy as np
    from .color_space import srgb_to_linear_rgb

    space = image.colorspace_settings
    if image.is_float and (space.is_data or space.name == "Linear Rec.709"):
        rgba = image_rgba(image)
    elif not image.is_float and space.name == "sRGB":
        rgba = image_rgba(image)
        rgba[..., :3] = srgb_to_linear_rgb(rgba[..., :3])
    else:
        rgba = decode_color_image(image, space.name)
    if image.is_float and image.alpha_mode in {"STRAIGHT", "PREMUL"}:
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


def estimate_highlight_threshold(image, *, panorama=False):
    """Estimate highlight onset from full RGB and spatial brightness contrast."""
    import numpy as np

    rgba = linear_color_rgba(image)
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


def prepare_material_color_input(source, bounds=None, rgba=None):
    """Export source bounds with interpretation matching the encoded color file."""
    import numpy as np
    from .hdr_image import save_hdr_image

    require_static_color_image(source)
    width, height = map(int, source.size)
    if (source.is_float and source.source == "FILE" and not source.is_dirty
            and not source.packed_files and source.alpha_mode == "STRAIGHT"):
        # Read the encoded float colors without applying a second alpha multiplication.
        reader = source.copy()
        try:
            reader.alpha_mode = "PREMUL"
            rgba = image_rgba(reader)
        finally:
            bpy.data.images.remove(reader)
    else:
        rgba = image_rgba(source) if rgba is None else np.asarray(rgba, dtype=np.float32)
    if rgba.shape != (height, width, 4):
        raise ValueError("The source RGBA does not match the Blender Image")
    left, top, right, bottom = (0, 0, width, height) if bounds is None else map(int, bounds)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("The material color bounds are outside the image")
    cropped = rgba[top:bottom, left:right]
    suffix = ".exr" if source.is_float else ".png"
    path = Path(tempfile.mkdtemp(prefix="anyimage-color-")) / ("color" + suffix)
    try:
        if source.is_float:
            # Store float colors directly; the EXR interpretation is applied on load.
            save_hdr_image(cropped, path)
        else:
            save_color_png(cropped, path, source.colorspace_settings.name)
        metadata = {
            "name": f"{image_base_name(source)}_color{suffix}",
            "color_space": "Linear Rec.709" if source.is_float else source.colorspace_settings.name,
            "alpha_mode": "PREMUL" if source.is_float and source.alpha_mode == "STRAIGHT" else source.alpha_mode,
            "color_normalized": bool(source.get(COLOR_NORMALIZED_PROPERTY)),
        }
        path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
        return path
    except Exception:
        cleanup_material_color_input(path)
        raise


def cleanup_material_color_input(path):
    """Release the directory owned by a prepared material color input."""
    if path:
        cleanup_image_input(Path(path).parent)


def load_material_color_image(path):
    """Load an independent packed Color image using its file interpretation."""
    path = Path(path)
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.name = metadata["name"]
        image.colorspace_settings.name = metadata["color_space"]
        image.alpha_mode = metadata["alpha_mode"]
        if metadata["color_normalized"]:
            image[COLOR_NORMALIZED_PROPERTY] = True
        image.pack()
        return image
    except Exception:
        bpy.data.images.remove(image)
        raise


@contextmanager
def material_color_image(
    source=None, *, bounds=None, rgba=None, input_path=None,
):
    """Own a prepared color image through material creation and clean failed results."""
    owned = input_path is None
    path = (
        prepare_material_color_input(source, bounds, rgba)
        if owned else Path(input_path)
    )
    image = None
    try:
        image = load_material_color_image(path)
        yield image
    except Exception:
        if image is not None:
            bpy.data.images.remove(image, do_unlink=True)
            image = None
        raise
    finally:
        if image is not None and image.users == 0:
            bpy.data.images.remove(image)
        if owned:
            cleanup_material_color_input(path)
