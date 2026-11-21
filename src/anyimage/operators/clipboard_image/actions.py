from dataclasses import dataclass

import bpy

from ...common.color_image import create_normalized_color_image
from ...common.image import (
    CLIPBOARD_HASH_PROPERTY,
    image_content_state,
    is_image_empty,
    restore_image_content,
    mark_image_empty_reference,
    has_other_image_user,
)
from ...common.viewport import redraw_area
from .cache import CLIPBOARD_CONTENT_PROPERTY
from .brush import PAINT_SETTINGS_BY_MODE, active_brush, set_brush_preview, set_tool_texture

REFERENCE_IMAGE_SIZE = 5.0
NODE_HEADER_HEIGHT = 20.0
NODE_TYPES = {
    "CompositorNodeTree": "CompositorNodeImage",
    "ShaderNodeTree": "ShaderNodeTexImage",
    "GeometryNodeTree": "GeometryNodeImageTexture",
}
WORLD_TEXTURE_NODE_TYPE = "ShaderNodeTexEnvironment"
IMAGE_NODE_TYPES = {*NODE_TYPES.values(), WORLD_TEXTURE_NODE_TYPE, "GeometryNodeInputImage"}

def target_for_context(context):
    area = getattr(context, "area", None)
    area_type = getattr(area, "type", None)
    if area_type == "VIEW_3D":
        mode = getattr(context, "mode", "OBJECT")
        if mode in PAINT_SETTINGS_BY_MODE:
            return "TOOL_TEXTURE"
        if mode == "OBJECT":
            return "IMAGE_EMPTY"
        return None
    if area_type != "NODE_EDITOR":
        return None

    tree_type = getattr(getattr(context, "space_data", None), "tree_type", None)
    if tree_type in NODE_TYPES:
        return "NODE"
    return None


@dataclass
class ClipboardImageTarget:
    """Identify the existing image and optional brush receiving pasted content."""

    image: object
    owner: object
    brush: object = None

    def assign_image(self, image):
        """Bind an image to the selected owner without changing its settings."""
        if is_image_empty(self.owner):
            self.owner.data = image
        else:
            _assign_node_image(self.owner, image)


def replacement_for_context(context):
    """Resolve a single image owner and validate its editable datablocks."""
    target = target_for_context(context)
    brush = None
    if target == "IMAGE_EMPTY":
        selected = getattr(context, "selected_objects", ())
        if len(selected) != 1 or not is_image_empty(selected[0]):
            return None
        owner = selected[0]
        image, owners = owner.data, (owner,)
    elif target == "NODE":
        space = context.space_data
        tree = getattr(space, "edit_tree", None) or getattr(space, "node_tree", None)
        if tree is None:
            return None
        selected = [node for node in tree.nodes if node.select]
        if len(selected) != 1 or selected[0].bl_idname not in IMAGE_NODE_TYPES:
            return None
        node = selected[0]
        owner = node
        image = getattr(node, "image", None)
        if not hasattr(node, "image"):
            socket = node.inputs.get("Image")
            if socket is None or socket.is_linked:
                return None
            image = socket.default_value
        owners = (tree,)
    elif target == "TOOL_TEXTURE":
        brush = active_brush(context)
        texture = getattr(brush, "texture", None)
        if texture is None or texture.type != "IMAGE":
            return None
        image, owners = texture.image, (brush, texture)
        owner = texture
    else:
        return None
    if image is None:
        return None
    if any(not owner.is_editable or owner.library is not None for owner in (*owners, image)):
        raise RuntimeError("The selected image and its owner must be editable")
    if image.source not in {"FILE", "GENERATED"}:
        raise RuntimeError("Clipboard replacement supports still images only")
    return ClipboardImageTarget(image, owner, brush)


def replace_pasted_image(context, target, image):
    """Replace one owner's content, isolating images used by other owners."""
    if min(image.size) <= 0:
        raise RuntimeError("The clipboard image has invalid dimensions")
    normalized = None
    source = target.image
    destination = source
    texture = None
    shared_texture = target.brush is not None and (
        target.brush.mask_texture == target.owner
        or any(user != target.brush and not isinstance(user, bpy.types.Screen)
               for user in bpy.data.user_map(subset={target.owner})[target.owner])
    )
    shared = shared_texture or has_other_image_user(target.owner)
    content = None
    try:
        if target.brush is not None and not image.is_float:
            normalized = create_normalized_color_image(image)
        if shared:
            destination = source.copy()
            destination.use_fake_user = False
        else:
            content = image_content_state(source)
        try:
            incoming = image_content_state(normalized if normalized is not None else image)
            incoming["filepath"] = image.filepath_raw
            # Install packed content before reloading a file-backed destination.
            restore_image_content(destination, incoming)
            if shared_texture:
                texture = target.owner.copy()
                texture.use_fake_user = False
                texture.image = destination
                target.brush.texture = texture
            elif shared:
                target.assign_image(destination)
            if target.brush is not None:
                target.brush.texture.update_tag()
                target.brush.update_tag()
        except Exception:
            if texture is not None:
                target.brush.texture = target.owner
                bpy.data.textures.remove(texture)
            elif shared:
                target.assign_image(source)
            if content is not None:
                restore_image_content(source, content)
            raise
        for key in (CLIPBOARD_HASH_PROPERTY, CLIPBOARD_CONTENT_PROPERTY):
            if key in destination:
                del destination[key]
        target.image = destination
        if destination != source and is_image_empty(target.owner):
            mark_image_empty_reference(source)
        if texture is not None:
            target.owner = texture
    finally:
        if destination != source and destination.users == 0:
            bpy.data.images.remove(destination)
        if normalized is not None:
            bpy.data.images.remove(normalized)
    try:
        if target.brush is not None and context.mode == "PAINT_TEXTURE":
            set_brush_preview(context, target.brush, target.image)
    finally:
        redraw_area(context)


def paste_image(context, image, location=None):
    target = target_for_context(context)
    if target == "IMAGE_EMPTY":
        return add_reference_image(context, image, location=location)
    if target == "NODE":
        return add_image_node(context, image, location=location)
    if target == "TOOL_TEXTURE":
        return set_tool_texture(context, image)
    raise RuntimeError("Paste images from a 3D View or Node Editor")


def add_reference_image(context, image, location=None):
    if getattr(context, "mode", "OBJECT") != "OBJECT":
        raise RuntimeError(
            "Switch to Object Mode before pasting a reference image"
        )

    width, height = image.size
    if width <= 0 or height <= 0:
        raise RuntimeError("The clipboard image has invalid dimensions")

    reference = bpy.data.objects.new(image.name, None)
    reference.empty_display_type = "IMAGE"
    reference.use_empty_image_alpha = True
    reference.data = image
    reference.empty_display_size = REFERENCE_IMAGE_SIZE
    try:
        context.collection.objects.link(reference)
        _place_in_view(context, reference, location)
        _select_only(context, reference)
    except Exception:
        bpy.data.objects.remove(reference, do_unlink=True)
        raise
    return reference


def _place_in_view(context, target_object, location=None):
    if location is None:
        location = context.scene.cursor.location
    target_object.location = location
    region_data = getattr(context, "region_data", None)
    if region_data is not None:
        target_object.rotation_euler = region_data.view_rotation.to_euler()


def _select_only(context, obj):
    for selected_object in getattr(context, "selected_objects", ()):
        selected_object.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def add_image_node(context, image, location=None):
    space = context.space_data
    node_tree = getattr(space, "edit_tree", None)
    if node_tree is None:
        node_tree = getattr(space, "node_tree", None)
    if node_tree is None:
        raise RuntimeError("The Node Editor has no editable node tree")

    node_type = _node_type_for_space(space)
    if node_type is None:
        raise RuntimeError(f"Unsupported node tree: {space.tree_type}")

    node = node_tree.nodes.new(node_type)
    try:
        _assign_node_image(node, image)
        node.location = _node_location(context, None) if location is None else location[:2]
        _select_only_node(node_tree, node)
    except Exception:
        node_tree.nodes.remove(node)
        raise
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
        raise RuntimeError("The image node has no assignable image input")
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
    if target == "IMAGE_EMPTY":
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
