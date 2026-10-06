"""Shared Blender Image and Image Empty lifecycle helpers."""

import shutil
import tempfile
from pathlib import Path

import bpy

image_content_handlers = []

TEMPORARY_IMAGE_PREVIEW_PROPERTY = "anyimage_temporary_preview"

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


def is_static_image(image):
    """Return whether an Image has valid dimensions and a static source."""
    try:
        width, height = (int(value) for value in image.size)
        return width > 0 and height > 0 and not is_animated_image(image)
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


def is_color_reference_candidate(image):
    """Return whether a static Image is selectable as a color reference."""
    if not is_static_image(image):
        return False
    try:
        get = getattr(image, "get", None)
        if get is not None and get(TEMPORARY_IMAGE_PREVIEW_PROPERTY, False):
            return False
        name = image_base_name(image)
        stem, separator, duplicate = name.rpartition(".")
        if separator and duplicate.isdigit():
            name = stem
        return not name.lower().endswith(("_normal", "_depth", "_color"))
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


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
        float_buffer=bool(getattr(source_image, "is_float", False)),
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
    preview = image.preview
    if preview is not None:
        preview.reload()
    for handler in tuple(image_content_handlers):
        handler(image)


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
