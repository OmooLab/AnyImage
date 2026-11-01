"""Prepare, interpret and normalize material color images."""

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import bpy

from .image import (
    COLOR_NORMALIZED_PROPERTY, cleanup_image_input, image_base_name, image_is_packed, image_rgba,
    is_animated_image, image_content_state, image_pixels, restore_image_content,
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


def configure_material_color_image(image, scene=None, *, panorama=False):
    """Preserve HDR, reverse panorama colors, and normalize surface colors."""
    if getattr(image, "is_float", False):
        return image
    if image.get(COLOR_NORMALIZED_PROPERTY) and not panorama:
        return image
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    preferred = material_color_space_name(scene)
    normalize = not panorama and preferred != "sRGB"
    pixels = (
        image_pixels(image)
        if getattr(image, "source", None) == "GENERATED"
        or getattr(image, "is_dirty", False)
        else None
    )
    settings = image.colorspace_settings
    original_space = settings.name
    original_alpha = image.alpha_mode
    original_content = image_content_state(image) if normalize else None
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
        if normalize and settings.name != "sRGB":
            import numpy as np
            from .color_space import normalize_color_rgba

            if pixels is not None:
                image.pixels.foreach_set(pixels)
            rgba = normalize_color_rgba(decode_color_image(image, settings.name))
            settings.name = "sRGB"
            image.alpha_mode = "PREMUL"
            image.pixels.foreach_set(np.flipud(rgba).ravel())
            image.update()
            image.pack()
            image[COLOR_NORMALIZED_PROPERTY] = True
            return image
        image.alpha_mode = color_alpha_mode(settings.name)
        if pixels is not None:
            image.pixels.foreach_set(pixels)
            image.update()
        if panorama and COLOR_NORMALIZED_PROPERTY in image:
            del image[COLOR_NORMALIZED_PROPERTY]
    except Exception:
        if original_content is not None:
            restore_image_content(image, original_content)
            raise
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


def median_color_luminance(image):
    """Return median linear luminance over finite, visible texture pixels."""
    import numpy as np
    from .color_space import srgb_to_linear_rgb

    if image.is_float:
        rgba = image_rgba(image)
    elif image.colorspace_settings.name == "sRGB":
        rgba = image_rgba(image)
        rgba[..., :3] = srgb_to_linear_rgb(rgba[..., :3])
    else:
        rgba = decode_color_image(image, image.colorspace_settings.name)
    visible = (rgba[..., 3] > 0) & np.isfinite(rgba).all(axis=-1)
    if not visible.any():
        return 0.0
    luminance = rgba[..., :3][visible] @ np.array((.2126, .7152, .0722), dtype=np.float32)
    return float(np.median(luminance))


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
    from .hdr_image import save_hdr_result

    require_static_color_image(source)
    width, height = map(int, source.size)
    if (source.is_float and source.source == "FILE" and not source.is_dirty
            and not image_is_packed(source) and source.alpha_mode == "STRAIGHT"):
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
            save_hdr_result(cropped, path)
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
