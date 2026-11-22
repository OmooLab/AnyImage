"""Bind pasted images to paint brushes and update their previews."""

from pathlib import Path
from tempfile import TemporaryDirectory

import bpy

from ...common.color_image import create_normalized_color_image
from ...common.image import COLOR_NORMALIZED_PROPERTY

CLIPBOARD_TEXTURE_PROPERTY = "anyimage_clipboard_texture"
DEFAULT_STENCIL_SIZE = 256.0
WHITE_BRUSH_COLOR_MODES = {
    "PAINT_TEXTURE",
    "PAINT_VERTEX",
}

PAINT_SETTINGS_BY_MODE = {
    "SCULPT": "sculpt",
    "PAINT_TEXTURE": "image_paint",
    "PAINT_VERTEX": "vertex_paint",
}


def set_tool_texture(context, image):
    brush = active_brush(context)
    if brush is None:
        raise RuntimeError("The active tool does not provide an editable brush")
    brush = _ensure_editable_brush(context, brush)

    normalized = None
    previous = (
        brush.texture, brush.texture_slot.texture,
        brush.texture_slot.map_mode, tuple(brush.stencil_dimension),
    )
    texture, is_new = None, False
    try:
        already_normalized = (
            image.get(COLOR_NORMALIZED_PROPERTY) and image.colorspace_settings.name == "sRGB"
            and image.alpha_mode == "PREMUL" and image.file_format == "PNG"
        )
        if not image.is_float and not already_normalized:
            normalized = create_normalized_color_image(image)
            image = normalized
        if not image.packed_file:
            image.pack()
        texture, is_new = _find_or_create_image_texture(image)
        brush.texture = texture
        brush.texture_slot.texture = texture
        brush.texture_slot.map_mode = "STENCIL"
        brush.stencil_dimension = _stencil_dimensions(
            image.size,
            brush.stencil_dimension,
        )
        if brush.texture != texture or brush.texture_slot.texture != texture:
            raise RuntimeError("Blender did not bind the texture to the active brush")
        _set_unbiased_paint_color(context, brush)
        brush.update_tag()
    except (AttributeError, TypeError, RuntimeError, ValueError) as error:
        (
            brush.texture, brush.texture_slot.texture,
            brush.texture_slot.map_mode, brush.stencil_dimension,
        ) = previous
        if is_new:
            bpy.data.textures.remove(texture)
        if normalized is not None:
            bpy.data.images.remove(normalized)
        raise RuntimeError(
            f"The active brush could not use the image texture: {error}"
        ) from error
    return texture


def set_brush_preview(context, brush, image):
    try:
        with TemporaryDirectory(prefix="anyimage-brush-") as directory:
            path = str(Path(directory) / "preview.png")
            original_format = image.file_format
            try:
                image.file_format = "PNG"
                image.save(filepath=path, save_copy=True)
            finally:
                image.file_format = original_format
            with context.temp_override(id=brush):
                result = bpy.ops.ed.lib_id_load_custom_preview(filepath=path)
            if result != {"FINISHED"}:
                raise RuntimeError("Blender did not load the custom preview")
    except (OSError, RuntimeError, ValueError) as error:
        raise RuntimeError(
            f"Texture pasted, but the brush preview could not be updated: {error}"
        ) from error


def _set_unbiased_paint_color(context, brush):
    if getattr(context, "mode", "") not in WHITE_BRUSH_COLOR_MODES:
        return

    white = (1.0, 1.0, 1.0)
    brush.color = white

    tool_settings = getattr(context, "tool_settings", None)
    if tool_settings is None:
        scene = getattr(context, "scene", None)
        tool_settings = getattr(scene, "tool_settings", None)

    paint_settings = getattr(tool_settings, PAINT_SETTINGS_BY_MODE[context.mode], None)
    unified_settings = getattr(paint_settings, "unified_paint_settings", None)
    if unified_settings is None:
        unified_settings = getattr(tool_settings, "unified_paint_settings", None)
    if unified_settings is not None:
        unified_settings.color = white


def _ensure_editable_brush(context, brush):
    brush_library = getattr(brush, "library", None)
    brush_is_editable = getattr(brush, "is_editable", True)
    if brush_library is None and brush_is_editable:
        return brush

    if brush_library is not None:
        return _copy_and_activate_library_brush(context, brush)

    make_local = getattr(brush, "make_local", None)
    if make_local is None:
        raise RuntimeError("The active brush is read-only and cannot be localized")

    # Brush Asset 可能来自外部库；先本地化，才能引用当前 .blend 中的 Texture。
    try:
        local_brush = make_local()
    except RuntimeError as error:
        raise RuntimeError(
            f"Unable to make the active brush local: {error}"
        ) from error

    if local_brush is None:
        local_brush = brush
    if getattr(local_brush, "library", None) is not None:
        raise RuntimeError("The active brush still belongs to an external library")
    if not getattr(local_brush, "is_editable", False):
        raise RuntimeError("The localized brush is still read-only")
    return local_brush


def _copy_and_activate_library_brush(context, brush):
    try:
        result = bpy.ops.brush.asset_save_as(
            name=f"{brush.name} Clipboard",
            asset_library_reference="LOCAL",
        )
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError(
            f"Unable to create a local copy of the active Brush Asset: {error}"
        ) from error

    if result != {"FINISHED"}:
        raise RuntimeError("Unable to activate the local Brush Asset copy")

    local_brush = active_brush(context)
    if local_brush is None or getattr(local_brush, "library", None) is not None:
        raise RuntimeError("Blender did not activate a local Brush Asset copy")
    return local_brush


def _find_or_create_image_texture(image):
    for texture in bpy.data.textures:
        if texture.type == "IMAGE" and texture.get(CLIPBOARD_TEXTURE_PROPERTY) and texture.image == image:
            return texture, False

    texture = bpy.data.textures.new(name=f"{image.name} Texture", type="IMAGE")
    texture.image = image
    texture[CLIPBOARD_TEXTURE_PROPERTY] = True
    return texture, True


def _stencil_dimensions(image_size, current_dimensions):
    width, height = image_size
    if width <= 0 or height <= 0:
        raise RuntimeError("The clipboard image has invalid dimensions")

    stencil_size = max(current_dimensions, default=DEFAULT_STENCIL_SIZE)
    if stencil_size <= 0:
        stencil_size = DEFAULT_STENCIL_SIZE
    if width >= height:
        return stencil_size, stencil_size * height / width
    return stencil_size * width / height, stencil_size


def active_brush(context):
    mode = getattr(context, "mode", "")
    tool_settings = getattr(context, "tool_settings", None)
    if tool_settings is None:
        scene = getattr(context, "scene", None)
        tool_settings = getattr(scene, "tool_settings", None)

    settings_name = PAINT_SETTINGS_BY_MODE.get(mode)
    if settings_name is not None:
        paint_settings = getattr(tool_settings, settings_name, None)
        brush = getattr(paint_settings, "brush", None)
        if brush is not None:
            return brush

    return getattr(context, "brush", None)
