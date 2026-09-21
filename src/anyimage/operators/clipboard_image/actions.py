import hashlib
import os
import tempfile

import bpy

from ...common.material import create_image_material
from ...common.color_image import material_color_image
from ...common.image import cleanup_image_input, image_pixels, save_packed_image

CLIPBOARD_HASH_PROPERTY = "anyimage_clipboard_sha256"
CLIPBOARD_CONTENT_PROPERTY = "anyimage_clipboard_content_sha256"
CLIPBOARD_TEXTURE_PROPERTY = "anyimage_clipboard_texture"
DEFAULT_STENCIL_SIZE = 256.0
REFERENCE_IMAGE_SIZE = 5.0
NODE_HEADER_HEIGHT = 20.0
NODE_TYPES = {
    "CompositorNodeTree": "CompositorNodeImage",
    "ShaderNodeTree": "ShaderNodeTexImage",
    "GeometryNodeTree": "GeometryNodeImageTexture",
}
WORLD_TEXTURE_NODE_TYPE = "ShaderNodeTexEnvironment"

BRUSH_TEXTURE_MODES = {
    "SCULPT",
    "PAINT_TEXTURE",
    "PAINT_VERTEX",
}

WHITE_BRUSH_COLOR_MODES = {
    "PAINT_TEXTURE",
    "PAINT_VERTEX",
}

PAINT_SETTINGS_BY_MODE = {
    "SCULPT": ("sculpt",),
    "PAINT_TEXTURE": ("image_paint",),
    "PAINT_VERTEX": ("vertex_paint",),
    "PAINT_WEIGHT": ("weight_paint",),
    "PAINT_GREASE_PENCIL": ("grease_pencil_paint", "gpencil_paint"),
    "VERTEX_GREASE_PENCIL": ("gpencil_vertex_paint",),
    "SCULPT_GREASE_PENCIL": ("grease_pencil_sculpt", "gpencil_sculpt_paint"),
    "WEIGHT_GREASE_PENCIL": ("grease_pencil_weight", "gpencil_weight_paint"),
    "SCULPT_CURVES": ("curves_sculpt",),
}


class PasteTargetError(RuntimeError):
    pass


class BrushPreviewError(RuntimeError):
    pass


def target_for_context(context):
    area = getattr(context, "area", None)
    area_type = getattr(area, "type", None)
    if area_type == "VIEW_3D":
        mode = getattr(context, "mode", "OBJECT")
        if mode in BRUSH_TEXTURE_MODES:
            return "TOOL_TEXTURE"
        if mode == "OBJECT":
            return "PLANE"
        return None
    if area_type != "NODE_EDITOR":
        return None

    tree_type = getattr(getattr(context, "space_data", None), "tree_type", None)
    if tree_type in NODE_TYPES:
        return "NODE"
    return None


def acquire_packed_image(image_data, suffix):
    image_hash = hashlib.sha256(image_data).hexdigest()
    existing_image = _find_packed_clipboard_image(image_hash)
    if existing_image is not None:
        return existing_image, True

    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix="blender-clipboard-",
        suffix=suffix,
    )
    image = None
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(image_data)
        image = bpy.data.images.load(temporary_path, check_existing=False)
        image.name = "Clipboard"
        image.pack()
        image[CLIPBOARD_HASH_PROPERTY] = image_hash
        image[CLIPBOARD_CONTENT_PROPERTY] = _clipboard_content_hash(image)
        return image, False
    except Exception:
        if image is not None:
            bpy.data.images.remove(image)
        raise
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _find_packed_clipboard_image(image_hash):
    for image in bpy.data.images:
        if image.get(CLIPBOARD_HASH_PROPERTY) != image_hash:
            continue
        if not _is_image_packed(image):
            continue
        baseline = image.get(CLIPBOARD_CONTENT_PROPERTY)
        if not baseline:
            continue
        try:
            if _clipboard_content_hash(image) == baseline:
                return image
        except (RuntimeError, ValueError, ReferenceError, OSError):
            continue
    return None


def _clipboard_content_hash(image):
    """Fingerprint current pixels and interpretation without changing the image."""
    digest = hashlib.sha256()
    digest.update(repr((tuple(image.size), image.colorspace_settings.name, image.alpha_mode)).encode())
    digest.update(image_pixels(image).tobytes())
    return digest.hexdigest()


def _is_image_packed(image):
    if getattr(image, "packed_file", None) is not None:
        return True
    return bool(getattr(image, "packed_files", ()))


def paste_image(
    context,
    image,
    event=None,
    import_as="REFERENCE",
    shadeless=False,
    location=None,
):
    target = target_for_context(context)
    if target == "PLANE":
        if location is None:
            location = paste_location(context, event)
        if import_as == "REFERENCE":
            return add_reference_image(context, image, location=location)
        return add_image_plane(
            context,
            image,
            location=location,
            shadeless=shadeless,
        )
    if target == "NODE":
        return add_image_node(context, image, event, location=location)
    if target == "TOOL_TEXTURE":
        return set_tool_texture(context, image)
    raise PasteTargetError("Paste images from a 3D View or Node Editor")


def add_image_plane(
    context,
    image,
    shadeless=False,
    location=None,
):
    if getattr(context, "mode", "OBJECT") != "OBJECT":
        raise PasteTargetError("Switch to Object Mode before pasting an image plane")

    width, height = image.size
    if width <= 0 or height <= 0:
        raise PasteTargetError("The clipboard image has invalid dimensions")

    from ..convert_to_plane.image_plane import create_image_plane_object

    half_width, half_height = _plane_half_dimensions(width, height)
    material = plane = None
    try:
        with material_color_image(image) as color:
            material = create_image_material(image, color, shadeless=shadeless, scene=context.scene)
            plane = create_image_plane_object(
                context, image.name, (-half_width, half_width, -half_height, half_height), material,
            )
            _place_in_view(context, plane, location)
            _select_only(context, plane)
    except Exception:
        if plane is not None:
            mesh = plane.data
            bpy.data.objects.remove(plane, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if material is not None and material.users == 0:
            bpy.data.materials.remove(material)
        raise
    return plane


def add_reference_image(context, image, location=None):
    if getattr(context, "mode", "OBJECT") != "OBJECT":
        raise PasteTargetError(
            "Switch to Object Mode before pasting a reference image"
        )

    width, height = image.size
    if width <= 0 or height <= 0:
        raise PasteTargetError("The clipboard image has invalid dimensions")

    reference = bpy.data.objects.new(image.name, None)
    reference.empty_display_type = "IMAGE"
    reference.use_empty_image_alpha = True
    reference.data = image
    reference.empty_display_size = REFERENCE_IMAGE_SIZE
    context.collection.objects.link(reference)
    _place_in_view(context, reference, location)
    _select_only(context, reference)
    return reference


def _place_in_view(context, target_object, location=None):
    if location is None:
        location = context.scene.cursor.location
    target_object.location = location
    region_data = getattr(context, "region_data", None)
    if region_data is not None:
        target_object.rotation_euler = region_data.view_rotation.to_euler()


def _plane_half_dimensions(width, height):
    if width >= height:
        return 1.0, height / width
    return width / height, 1.0


def _select_only(context, plane):
    for selected_object in getattr(context, "selected_objects", ()):
        selected_object.select_set(False)
    plane.select_set(True)
    context.view_layer.objects.active = plane


def add_image_node(context, image, event=None, location=None):
    space = context.space_data
    node_tree = getattr(space, "edit_tree", None)
    if node_tree is None:
        node_tree = getattr(space, "node_tree", None)
    if node_tree is None:
        raise PasteTargetError("The Node Editor has no editable node tree")

    node_type = _node_type_for_space(space)
    if node_type is None:
        raise PasteTargetError(f"Unsupported node tree: {space.tree_type}")

    node = node_tree.nodes.new(node_type)
    _assign_node_image(node, image)
    if location is None:
        location = _node_location(context, event)
    node.location = location
    _select_only_node(node_tree, node)
    return node


def _node_type_for_space(space):
    if _is_world_shader_space(space):
        return WORLD_TEXTURE_NODE_TYPE
    return NODE_TYPES.get(getattr(space, "tree_type", None))


def _is_world_shader_space(space):
    if getattr(space, "tree_type", None) != "ShaderNodeTree":
        return False
    if getattr(space, "shader_type", None) == "WORLD":
        return True

    owner_id = getattr(space, "id", None)
    owner_rna = getattr(owner_id, "bl_rna", None)
    return getattr(owner_rna, "identifier", None) == "World"


def _assign_node_image(node, image):
    if hasattr(node, "image"):
        node.image = image
        return

    # Geometry Nodes 的 Image Texture 把图片存在 Image socket，而非 node.image。
    image_input = node.inputs.get("Image")
    if image_input is None or not hasattr(image_input, "default_value"):
        raise PasteTargetError("The image node has no assignable image input")
    image_input.default_value = image


def _node_location(context, event):
    if event is not None:
        region = getattr(context, "region", None)
        view2d = getattr(region, "view2d", None)
        if view2d is not None:
            view_x, view_y = view2d.region_to_view(
                event.mouse_region_x,
                event.mouse_region_y,
            )
            system = getattr(getattr(context, "preferences", None), "system", None)
            ui_scale = float(getattr(system, "ui_scale", 1.0) or 1.0)
            return (
                (view_x - NODE_HEADER_HEIGHT * 1.5) / ui_scale,
                (view_y + NODE_HEADER_HEIGHT * 0.5) / ui_scale,
            )

    cursor_location = getattr(context.space_data, "cursor_location", None)
    if cursor_location is not None:
        return cursor_location
    return (0.0, 0.0)


def paste_location(context, event=None):
    target = target_for_context(context)
    if target == "PLANE":
        return _view3d_location(context, event)
    if target == "NODE":
        return _node_location(context, event)
    return None


def _view3d_location(context, event=None):
    cursor_location = context.scene.cursor.location
    if event is None:
        return cursor_location.copy()

    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    if region is None or region_data is None:
        return cursor_location.copy()

    from bpy_extras.view3d_utils import region_2d_to_location_3d

    return region_2d_to_location_3d(
        region,
        region_data,
        (event.mouse_region_x, event.mouse_region_y),
        cursor_location,
    )


def _select_only_node(node_tree, node):
    for existing_node in node_tree.nodes:
        existing_node.select = False
    node.select = True
    node_tree.nodes.active = node


def set_tool_texture(context, image):
    brush = _active_brush(context)
    if brush is None:
        raise PasteTargetError("The active tool does not provide an editable brush")
    brush = _ensure_editable_brush(context, brush)

    texture, is_new = _find_or_create_image_texture(image)
    try:
        brush.texture = texture
        brush.texture_slot.texture = texture
        brush.texture_slot.map_mode = "STENCIL"
        brush.stencil_dimension = _stencil_dimensions(
            image.size,
            brush.stencil_dimension,
        )
        if brush.texture != texture or brush.texture_slot.texture != texture:
            raise PasteTargetError("Blender did not bind the texture to the active brush")
        _set_unbiased_paint_color(context, brush)
        brush.update_tag()
    except (AttributeError, TypeError, RuntimeError) as error:
        if is_new:
            bpy.data.textures.remove(texture)
        raise PasteTargetError(
            f"The active brush could not use the image texture: {error}"
        ) from error
    try:
        if getattr(context, "mode", "") == "PAINT_TEXTURE":
            _set_brush_preview(context, brush, image)
    finally:
        _redraw_area(context)
    return texture


def _set_brush_preview(context, brush, image):
    preview_path = None
    try:
        preview_path = save_packed_image(image, context.scene)
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
            cleanup_image_input(preview_path, True)


def _set_unbiased_paint_color(context, brush):
    if getattr(context, "mode", "") not in WHITE_BRUSH_COLOR_MODES:
        return

    white = (1.0, 1.0, 1.0)
    brush.color = white

    tool_settings = getattr(context, "tool_settings", None)
    if tool_settings is None:
        scene = getattr(context, "scene", None)
        tool_settings = getattr(scene, "tool_settings", None)

    unified_settings = None
    mode = getattr(context, "mode", "")
    for settings_name in PAINT_SETTINGS_BY_MODE.get(mode, ()):
        paint_settings = getattr(tool_settings, settings_name, None)
        unified_settings = getattr(
            paint_settings,
            "unified_paint_settings",
            None,
        )
        if unified_settings is not None:
            break
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
        raise PasteTargetError("The active brush is read-only and cannot be localized")

    # Brush Asset 可能来自外部库；先本地化，才能引用当前 .blend 中的 Texture。
    try:
        local_brush = make_local()
    except RuntimeError as error:
        raise PasteTargetError(
            f"Unable to make the active brush local: {error}"
        ) from error

    if local_brush is None:
        local_brush = brush
    if getattr(local_brush, "library", None) is not None:
        raise PasteTargetError("The active brush still belongs to an external library")
    if not getattr(local_brush, "is_editable", False):
        raise PasteTargetError("The localized brush is still read-only")
    return local_brush


def _copy_and_activate_library_brush(context, brush):
    try:
        result = bpy.ops.brush.asset_save_as(
            name=f"{brush.name} Clipboard",
            asset_library_reference="LOCAL",
        )
    except (AttributeError, RuntimeError) as error:
        raise PasteTargetError(
            f"Unable to create a local copy of the active Brush Asset: {error}"
        ) from error

    if result != {"FINISHED"}:
        raise PasteTargetError("Unable to activate the local Brush Asset copy")

    active_brush = _active_brush(context)
    if active_brush is None or getattr(active_brush, "library", None) is not None:
        raise PasteTargetError("Blender did not activate a local Brush Asset copy")
    return active_brush


def _find_or_create_image_texture(image):
    for texture in bpy.data.textures:
        if not texture.get(CLIPBOARD_TEXTURE_PROPERTY, False):
            continue
        if texture.image == image:
            return texture, False

    texture = bpy.data.textures.new(name=f"{image.name} Texture", type="IMAGE")
    texture.image = image
    texture[CLIPBOARD_TEXTURE_PROPERTY] = True
    return texture, True


def _stencil_dimensions(image_size, current_dimensions):
    width, height = image_size
    if width <= 0 or height <= 0:
        raise PasteTargetError("The clipboard image has invalid dimensions")

    stencil_size = max(current_dimensions, default=DEFAULT_STENCIL_SIZE)
    if stencil_size <= 0:
        stencil_size = DEFAULT_STENCIL_SIZE
    if width >= height:
        return stencil_size, stencil_size * height / width
    return stencil_size * width / height, stencil_size


def _active_brush(context):
    mode = getattr(context, "mode", "")
    tool_settings = getattr(context, "tool_settings", None)
    if tool_settings is None:
        scene = getattr(context, "scene", None)
        tool_settings = getattr(scene, "tool_settings", None)

    for settings_name in PAINT_SETTINGS_BY_MODE.get(mode, ()):
        paint_settings = getattr(tool_settings, settings_name, None)
        brush = getattr(paint_settings, "brush", None)
        if brush is not None:
            return brush

    return getattr(context, "brush", None)


def _redraw_area(context):
    area = getattr(context, "area", None)
    tag_redraw = getattr(area, "tag_redraw", None)
    if tag_redraw is not None:
        tag_redraw()
