"""Bind pasted images to paint brushes and update their previews."""

import bpy

from ...common.color_image import create_normalized_color_image
from ...common.image import image_content_state, replace_image_content, restore_image_content
from ...common.image_input import cleanup_image_input, save_image_input
from ...common.viewport import redraw_area

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


class BrushPreviewError(RuntimeError):
    pass


def set_tool_texture(context, image):
    brush = active_brush(context)
    if brush is None:
        raise RuntimeError("The active tool does not provide an editable brush")
    brush = _ensure_editable_brush(context, brush)

    content = None
    previous = (
        brush.texture, brush.texture_slot.texture,
        brush.texture_slot.map_mode, tuple(brush.stencil_dimension),
    )
    texture, is_new = None, False
    try:
        if not image.is_float:
            normalized = create_normalized_color_image(image)
            try:
                content = image_content_state(image)
                replace_image_content(image, normalized)
            finally:
                bpy.data.images.remove(normalized)
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
        if content is not None:
            restore_image_content(image, content)
        raise RuntimeError(
            f"The active brush could not use the image texture: {error}"
        ) from error
    try:
        if getattr(context, "mode", "") == "PAINT_TEXTURE":
            set_brush_preview(context, brush, image)
    finally:
        redraw_area(context)
    return texture


def set_brush_preview(context, brush, image):
    preview_path = None
    try:
        preview_path = save_image_input(image)
        with context.temp_override(id=brush):
            result = bpy.ops.ed.lib_id_load_custom_preview(filepath=str(preview_path))
        if result != {"FINISHED"}:
            raise RuntimeError("Blender did not load the custom preview")
    except (OSError, RuntimeError, ValueError) as error:
        raise BrushPreviewError(
            f"Texture pasted, but the brush preview could not be updated: {error}"
        ) from error
    finally:
        if preview_path is not None:
            cleanup_image_input(preview_path)


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
