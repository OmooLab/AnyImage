"""Shared Blender Image and Image Empty lifecycle helpers."""

import math
import shutil
import tempfile
from pathlib import Path

import bpy


VIEW_TRANSFORM_COLOR_SPACES = (
    ("ACES 1.3", "ACES 1.3 sRGB"),
    ("ACES 2.0", "ACES 2.0 sRGB"),
    ("AgX", "AgX Base sRGB"),
    ("Filmic", "Filmic sRGB"),
    ("Khronos PBR Neutral", "Khronos PBR Neutral sRGB"),
)

IMAGE_NAME_SUFFIXES = (
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
    ".tiff",
    ".tif",
    ".exr",
    ".hdr",
    ".bmp",
    ".tga",
)

MAX_PROJECTIVE_OUTPUT_DIMENSION = 8192
MAX_PROJECTIVE_OUTPUT_PIXELS = 16_777_216
PROJECTIVE_CHUNK_ROWS = 256


def is_image_empty(candidate):
    return bool(
        candidate
        and getattr(candidate, "type", None) == "EMPTY"
        and getattr(candidate, "empty_display_type", None) == "IMAGE"
        and getattr(candidate, "data", None) is not None
    )


def require_image_empty(object_name):
    """Return a named Image Empty or raise when it is no longer available."""
    source_object = bpy.data.objects.get(object_name)
    if not is_image_empty(source_object):
        raise RuntimeError("The source Image Empty is no longer available")
    return source_object


def image_pixels(image):
    """Read straight-alpha business pixels without changing presentation mode."""
    import numpy as np

    reader = image
    if (
        getattr(image, "alpha_mode", None) == "PREMUL"
        and not getattr(image, "is_dirty", False)
        and not getattr(image, "is_float", False)
        and getattr(image, "source", None) != "GENERATED"
    ):
        reader = image.copy()
    try:
        if reader is not image:
            reader.alpha_mode = "STRAIGHT"
        pixels = np.empty(len(reader.pixels), dtype=np.float32)
        reader.pixels.foreach_get(pixels)
    finally:
        if reader is not image:
            bpy.data.images.remove(reader)
    return pixels


def image_rgba(image):
    """Read one Blender Image into a top-down RGBA float32 array."""
    import numpy as np

    width, height = (int(value) for value in image.size)
    if width <= 0 or height <= 0:
        raise ValueError("The source image has no readable dimensions")
    return np.flipud(image_pixels(image).reshape((height, width, 4)))


def panorama_crop_bounds(width, height):
    """Return the largest centered integer-pixel 2:1 bounds."""
    width, height = int(width), int(height)
    crop_height = min(height, width // 2)
    crop_width = crop_height * 2
    if crop_width <= 0 or crop_height <= 0:
        raise ValueError("Panorama conversion requires an image at least 2 x 1 pixels")
    left = (width - crop_width) // 2
    top = (height - crop_height) // 2
    return left, top, left + crop_width, top + crop_height


def homography_from_points(source, target):
    """Return a projective transform mapping four source points to target."""
    import numpy as np

    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    if source.shape != (4, 2) or target.shape != (4, 2):
        raise ValueError("A homography requires four source and target points")
    rows = []
    values = []
    for (x, y), (u, v) in zip(source, target):
        rows.extend(
            (
                (x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y),
                (0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y),
            )
        )
        values.extend((u, v))
    matrix = np.asarray(rows, dtype=np.float64)
    if np.linalg.cond(matrix) > 1e12:
        raise ValueError("The projective transform is too degenerate")
    coefficients = np.linalg.solve(matrix, np.asarray(values, dtype=np.float64))
    return np.append(coefficients, 1.0).reshape((3, 3))


def transform_homography(points, matrix):
    """Transform 2D points by one homography."""
    import numpy as np

    points = np.asarray(points, dtype=np.float64)
    if points.ndim < 2 or points.shape[-1] != 2:
        raise ValueError("Projective points must contain X and Y")
    flat = points.reshape((-1, 2))
    homogeneous = np.column_stack((flat, np.ones(len(flat), dtype=np.float64)))
    mapped = homogeneous @ np.asarray(matrix, dtype=np.float64).T
    denominator = mapped[:, 2]
    if np.any(np.abs(denominator) <= 1e-12):
        raise ValueError("The projective transform reaches infinity")
    mapped = mapped[:, :2] / denominator[:, None]
    if not np.isfinite(mapped).all():
        raise ValueError("The projective transform is not finite")
    return mapped.reshape(points.shape)


def projective_output_size(
    quad,
    aspect_ratio,
    max_dimension=MAX_PROJECTIVE_OUTPUT_DIMENSION,
    max_pixels=MAX_PROJECTIVE_OUTPUT_PIXELS,
):
    """Choose a detail-preserving output size for a source-space quad."""
    import numpy as np

    quad = np.asarray(quad, dtype=np.float64)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Projective output requires four valid corners")
    if not math.isfinite(aspect_ratio) or aspect_ratio <= 0.0:
        raise ValueError("Projective output aspect ratio must be greater than zero")
    width_pixels = 0.5 * (
        np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])
    )
    height_pixels = 0.5 * (
        np.linalg.norm(quad[2] - quad[1]) + np.linalg.norm(quad[3] - quad[0])
    )
    if min(width_pixels, height_pixels) <= 1e-8:
        raise ValueError("Projective output corners are too close together")
    height = (aspect_ratio * width_pixels + height_pixels) / (
        aspect_ratio * aspect_ratio + 1.0
    )
    width = aspect_ratio * height
    dimension_scale = float(max_dimension) / max(width, height)
    pixel_scale = math.sqrt(float(max_pixels) / max(width * height, 1.0))
    scale = min(1.0, dimension_scale, pixel_scale)
    return max(2, int(round(width * scale))), max(2, int(round(height * scale)))


def premultiplied_rgba(source_pixels, source_size):
    """Return top-down premultiplied RGBA pixels."""
    import numpy as np

    width, height = (int(value) for value in source_size)
    if min(width, height) <= 0:
        raise ValueError("Image dimensions must be positive")
    source = np.asarray(source_pixels, dtype=np.float32)
    if source.size != width * height * 4:
        raise ValueError("The image pixels do not match its dimensions")
    source = np.flipud(source.reshape((height, width, 4))).copy()
    source[:, :, :3] *= source[:, :, 3:4]
    return source


def sample_rgba(source, source_points):
    """Bilinearly sample top-down RGBA at image-boundary coordinates."""
    import numpy as np

    source = np.asarray(source, dtype=np.float32)
    points = np.asarray(source_points, dtype=np.float64)
    if source.ndim != 3 or source.shape[2] != 4:
        raise ValueError("The source must contain RGBA pixels")
    if points.shape[-1] != 2:
        raise ValueError("Sample points must contain X and Y")
    height, width = source.shape[:2]
    flat = points.reshape((-1, 2))
    mapped_x = flat[:, 0]
    mapped_y = flat[:, 1]
    valid = (
        np.isfinite(mapped_x)
        & np.isfinite(mapped_y)
        & (mapped_x >= 0.0)
        & (mapped_x <= width)
        & (mapped_y >= 0.0)
        & (mapped_y <= height)
    )
    pixel_x = np.clip(mapped_x - 0.5, 0.0, width - 1.0)
    pixel_y = np.clip(mapped_y - 0.5, 0.0, height - 1.0)
    x0 = np.floor(pixel_x).astype(np.int64)
    y0 = np.floor(pixel_y).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = (pixel_x - x0)[:, None]
    fy = (pixel_y - y0)[:, None]
    sampled = (
        source[y0, x0] * (1.0 - fx) * (1.0 - fy)
        + source[y0, x1] * fx * (1.0 - fy)
        + source[y1, x0] * (1.0 - fx) * fy
        + source[y1, x1] * fx * fy
    )
    sampled[~valid] = 0.0
    return sampled.reshape((*points.shape[:-1], 4))


def straight_rgba(premultiplied):
    """Convert premultiplied RGBA and bleed edge RGB into transparent pixels."""
    import numpy as np

    rgba = np.asarray(premultiplied, dtype=np.float32).copy()
    alpha = rgba[..., 3]
    visible = alpha > 1e-8
    rgb = rgba[..., :3]
    rgb[visible] /= alpha[visible, None]
    rgba[~visible] = 0.0
    if rgba.ndim == 3:
        unfilled = ~visible

        def fill_edge(target, source):
            candidates = unfilled[target] & visible[source]
            target_rgb = rgb[target]
            target_rgb[candidates] = rgb[source][candidates]
            unfilled[target][candidates] = False

        fill_edge((slice(1, None), slice(None)), (slice(None, -1), slice(None)))
        fill_edge((slice(None, -1), slice(None)), (slice(1, None), slice(None)))
        fill_edge((slice(None), slice(1, None)), (slice(None), slice(None, -1)))
        fill_edge((slice(None), slice(None, -1)), (slice(None), slice(1, None)))
        fill_edge((slice(1, None), slice(1, None)), (slice(None, -1), slice(None, -1)))
        fill_edge((slice(1, None), slice(None, -1)), (slice(None, -1), slice(1, None)))
        fill_edge((slice(None, -1), slice(1, None)), (slice(1, None), slice(None, -1)))
        fill_edge((slice(None, -1), slice(None, -1)), (slice(1, None), slice(1, None)))
    return rgba


def warp_projective_pixels(source_pixels, source_size, quad, output_size):
    """Warp one source quad into Blender-order straight RGBA pixels."""
    import numpy as np

    output_width, output_height = (int(value) for value in output_size)
    if min(output_width, output_height) <= 0:
        raise ValueError("Projective output dimensions must be positive")
    source = premultiplied_rgba(source_pixels, source_size)
    target = np.asarray(
        (
            (0.0, 0.0),
            (float(output_width), 0.0),
            (float(output_width), float(output_height)),
            (0.0, float(output_height)),
        ),
        dtype=np.float64,
    )
    output_to_source = homography_from_points(target, quad)
    output = np.zeros((output_height, output_width, 4), dtype=np.float32)
    target_x = np.arange(output_width, dtype=np.float64) + 0.5
    for row_start in range(0, output_height, PROJECTIVE_CHUNK_ROWS):
        row_end = min(row_start + PROJECTIVE_CHUNK_ROWS, output_height)
        target_y = np.arange(row_start, row_end, dtype=np.float64) + 0.5
        x, y = np.meshgrid(target_x, target_y)
        points = np.stack((x, y), axis=-1)
        mapped = transform_homography(points, output_to_source)
        output[row_start:row_end] = sample_rgba(source, mapped)
    return np.flipud(straight_rgba(output)).ravel()


def is_animated_image(image):
    return getattr(image, "source", None) in {"MOVIE", "SEQUENCE"}


def image_user_settings(source_object):
    """Return an image owner's playback settings as a four-item tuple."""
    image_user = getattr(source_object, "image_user", None)
    if image_user is None:
        return 1, 0, 0, False
    return (
        int(getattr(image_user, "frame_start", 1) or 1),
        int(getattr(image_user, "frame_offset", 0) or 0),
        int(getattr(image_user, "frame_duration", 0) or 0),
        bool(getattr(image_user, "use_cyclic", False)),
    )


def image_path(image):
    filepath_from_user = getattr(image, "filepath_from_user", None)
    filepath = (
        filepath_from_user()
        if callable(filepath_from_user)
        else getattr(image, "filepath", "")
    )
    if not filepath:
        return Path()
    return Path(bpy.path.abspath(filepath)).expanduser()


def image_is_packed(image):
    if getattr(image, "packed_file", None) is not None:
        return True
    return bool(getattr(image, "packed_files", ()))


def cleanup_image_input(path, temporary):
    """Remove a prepared input and its temporary container when requested."""
    if not temporary or not path:
        return
    path = Path(path)
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
    except OSError:
        pass


def image_base_name(image):
    name = image.name
    lower_name = name.lower()
    for suffix in IMAGE_NAME_SUFFIXES:
        suffix_index = lower_name.rfind(suffix)
        if suffix_index <= 0:
            continue
        trailing = name[suffix_index + len(suffix) :]
        if trailing and not (
            trailing.startswith(".") and trailing[1:].isdigit()
        ):
            continue
        return f"{name[:suffix_index]}{trailing}"
    return name


def depth_data_name(source_object):
    return f"{image_base_name(source_object.data)}_depth.exr"


def normal_data_name(source_object):
    return f"{image_base_name(source_object.data)}_normal.png"


def save_packed_image(image, _scene):
    output_path = Path(tempfile.mkdtemp(prefix="anyimage-input-")) / "input.png"
    original_file_format = image.file_format
    try:
        image.file_format = "PNG"
        image.save(filepath=str(output_path), save_copy=True)
    except (OSError, RuntimeError, ValueError) as error:
        cleanup_image_input(output_path, True)
        raise RuntimeError("Unable to export the packed image") from error
    finally:
        image.file_format = original_file_format
    if not output_path.is_file():
        cleanup_image_input(output_path, True)
        raise RuntimeError("Blender did not export the packed image")
    return output_path


def prepare_image_input(image, scene):
    """Prepare one still image for a Server job."""
    if is_animated_image(image):
        raise RuntimeError("Only still images are supported")
    if image_is_packed(image):
        return save_packed_image(image, scene), True
    source_path = image_path(image)
    if not source_path.is_file():
        raise RuntimeError(f"Source image file does not exist: {source_path}")
    return source_path, False


def load_image_edit_result(source_image, output_path):
    """Load and pack the image file returned by a Job."""
    output_path = Path(output_path)
    if not output_path.is_file():
        raise RuntimeError(f"Color result image does not exist: {output_path}")
    result_image = None
    try:
        result_image = bpy.data.images.load(str(output_path), check_existing=False)
        result_image.colorspace_settings.name = source_image.colorspace_settings.name
        result_image.alpha_mode = source_image.alpha_mode
        result_image.pack()
        result_image.name = source_image.name
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        if result_image is not None:
            bpy.data.images.remove(result_image, do_unlink=True)
        raise RuntimeError("Unable to load the color result") from error
    return result_image


def load_normal_result_image(path, source_object):
    """Load, name, configure, and pack a generated normal image."""
    image = bpy.data.images.load(str(path), check_existing=False)
    image.name = normal_data_name(source_object)
    image.colorspace_settings.name = "Non-Color"
    image.pack()
    return image


def color_alpha_mode(color_space):
    """Pair inverse view color spaces with straight alpha."""
    return "STRAIGHT" if color_space in dict(VIEW_TRANSFORM_COLOR_SPACES).values() else "PREMUL"


def create_image_edit_result(source_image, pixels, output_size):
    """Create a packed Image datablock from edited RGBA pixels."""
    output_width, output_height = (int(value) for value in output_size)
    if output_width <= 0 or output_height <= 0:
        raise ValueError("The edited image dimensions must be positive")
    if len(pixels) != output_width * output_height * 4:
        raise ValueError("The edited pixels do not match the image dimensions")
    image = bpy.data.images.new(
        source_image.name,
        width=output_width,
        height=output_height,
        alpha=True,
    )
    try:
        image.colorspace_settings.name = source_image.colorspace_settings.name
        image.alpha_mode = source_image.alpha_mode
        image.pixels.foreach_set(pixels)
        image.pack()
        image.update()
    except Exception:
        bpy.data.images.remove(image, do_unlink=True)
        raise
    return image


def has_other_image_empty(source_object, *, removed_objects=()):
    """Check surviving image Empty objects for the same Image datablock."""
    return any(
        candidate != source_object
        and candidate not in removed_objects
        and is_image_empty(candidate)
        and candidate.data == source_object.data
        for candidate in bpy.data.objects
    )


def require_conversion_source(operator):
    """Validate the object and image captured when a conversion was submitted."""
    source = require_image_empty(operator.source_object_name)
    if (str(source.as_pointer()) != operator.source_identity
            or str(source.data.as_pointer()) != operator.image_identity):
        raise ValueError("The conversion source image has changed")
    return source


def image_content_state(image):
    """Capture encoded content and unsaved pixels for an Image transaction."""
    import numpy as np

    pixels = None
    if image.is_dirty:
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
    return {
        "source": image.source,
        "filepath": image.filepath_raw,
        "colorspace": image.colorspace_settings.name,
        "alpha_mode": image.alpha_mode,
        "file_format": image.file_format,
        "packed": bytes(image.packed_file.data) if image.packed_file else None,
        "pixels": pixels,
        "size": tuple(image.size),
        "generated": {
            name: getattr(image, name)
            for name in ("generated_width", "generated_height", "generated_type",
                         "use_generated_float")
        },
        "generated_color": tuple(image.generated_color),
    }


def restore_image_content(image, state):
    """Apply captured image content while retaining the destination ID."""
    if image.packed_file:
        image.source = "FILE"
        image.unpack(method="REMOVE")
    image.filepath_raw = state["filepath"]
    image.source = state["source"]
    if state["source"] == "GENERATED":
        for name, value in state["generated"].items():
            setattr(image, name, value)
        image.generated_color = state["generated_color"]
    image.colorspace_settings.name = state["colorspace"]
    image.alpha_mode = state["alpha_mode"]
    image.file_format = state["file_format"]
    if state["packed"] is not None:
        data = state["packed"]
        image.source = "FILE"
        image.pack(data=data, data_len=len(data))
        image.source = state["source"]
    image.reload()
    if state["pixels"] is not None:
        if tuple(image.size) != state["size"]:
            image.scale(*state["size"])
        image.pixels.foreach_set(state["pixels"])
        image.update()


def replace_empty_image(source_object, result_image, *, placement_bounds=None,
                        removed_objects=(), isolate_image=False):
    """Replace one Empty image, retaining shared source images."""
    try:
        source_image = source_object.data
        original_fake_user = source_image.use_fake_user
        original_blending = getattr(source_object, "use_empty_image_alpha", False)
        image_user = getattr(source_object, "image_user", None)
        original_timing = image_user_settings(source_object) if image_user is not None else None
        original_auto_refresh = getattr(image_user, "use_auto_refresh", False)
        alignment = (
            empty_display_alignment(
                source_object,
                tuple(source_image.size),
                tuple(result_image.size),
                placement_bounds,
            )
            if placement_bounds is not None
            else None
        )

        source_image.use_fake_user = True
        original_alignment = (
            (source_object.empty_display_size, tuple(source_object.empty_image_offset))
            if alignment is not None else None
        )
        original_content = None
        try:
            shared = isolate_image or has_other_image_empty(source_object, removed_objects=removed_objects)
            if shared:
                final_image = result_image
            else:
                result_content = image_content_state(result_image)
                original_content = image_content_state(source_image)
                restore_image_content(source_image, result_content)
                final_image = source_image
            source_object.data = final_image
            source_object.use_empty_image_alpha = True
            if alignment is not None:
                source_object.empty_display_size = alignment[0]
                source_object.empty_image_offset = alignment[1]
        except Exception:
            if original_content is not None:
                restore_image_content(source_image, original_content)
            source_object.data = source_image
            source_object.use_empty_image_alpha = original_blending
            if original_alignment is not None:
                source_object.empty_display_size, source_object.empty_image_offset = original_alignment
            if original_timing is not None:
                (image_user.frame_start, image_user.frame_offset,
                 image_user.frame_duration, image_user.use_cyclic) = original_timing
                image_user.use_auto_refresh = original_auto_refresh
            source_image.use_fake_user = original_fake_user
            raise

        source_image.use_fake_user = original_fake_user
        return final_image
    finally:
        if result_image.users == 0:
            bpy.data.images.remove(result_image)


def image_empty_bounds(source_object):
    image_width, image_height = source_object.data.size
    if image_width <= 0 or image_height <= 0:
        raise ValueError("The source image has no readable dimensions")

    aspect = image_width / image_height
    display_size = float(source_object.empty_display_size)
    if aspect >= 1.0:
        width = display_size
        height = display_size / aspect
    else:
        width = display_size * aspect
        height = display_size

    offset = source_object.empty_image_offset
    x_min = float(offset[0]) * width
    y_min = float(offset[1]) * height
    return (
        x_min,
        x_min + width,
        y_min,
        y_min + height,
    )


def empty_display_alignment(
    source_object,
    source_size,
    output_size,
    placement_bounds,
):
    """Return the display size and offset for an edited Image Empty."""
    source_width, source_height = source_size
    output_width, output_height = output_size
    left, top, right, bottom = placement_bounds
    if (
        source_width <= 0
        or source_height <= 0
        or output_width <= 0
        or output_height <= 0
        or right <= left
        or bottom <= top
    ):
        raise ValueError("The edited image placement is invalid")
    x_min, x_max, y_min, y_max = image_empty_bounds(source_object)
    local_width = x_max - x_min
    local_height = y_max - y_min
    desired_x_min = x_min + left * local_width / source_width
    desired_x_max = x_min + right * local_width / source_width
    desired_y_max = y_max - top * local_height / source_height
    desired_y_min = y_max - bottom * local_height / source_height
    desired_width = desired_x_max - desired_x_min
    desired_height = desired_y_max - desired_y_min
    display_size = max(desired_width, desired_height)
    aspect = output_width / output_height
    if aspect >= 1.0:
        display_width = display_size
        display_height = display_size / aspect
    else:
        display_width = display_size * aspect
        display_height = display_size
    center_x = (desired_x_min + desired_x_max) * 0.5
    center_y = (desired_y_min + desired_y_max) * 0.5
    return display_size, (
        center_x / display_width - 0.5,
        center_y / display_height - 0.5,
    )
