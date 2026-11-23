"""Resolve and commit image edits for image owners."""

from dataclasses import dataclass
from uuid import uuid4
from weakref import WeakValueDictionary

import bpy

from .image import (
    TEMPORARY_IMAGE_PREVIEW_PROPERTY,
    image_content_state,
    pack_image_result,
    has_other_image_user,
    image_pixels,
    image_rgba,
    is_static_image,
    owner_image,
    image_user_settings,
    is_animated_image,
    is_image_empty,
    replace_empty_image,
    restore_image_content,
)

_image_targets = WeakValueDictionary()


def active_texture_node(context):
    """Return the editable texture in the current material or World shader tree."""
    space = getattr(context, "space_data", None)
    if (
        getattr(space, "type", None) != "NODE_EDITOR"
        or getattr(space, "tree_type", None) != "ShaderNodeTree"
    ):
        return None
    shader = getattr(space, "shader_type", None)
    owner = getattr(space, "id", None)
    if shader == "WORLD" and isinstance(owner, bpy.types.World):
        types = {"ShaderNodeTexEnvironment", "ShaderNodeTexImage"}
    elif shader == "OBJECT" and isinstance(owner, bpy.types.Material):
        types = {"ShaderNodeTexImage"}
    else:
        return None
    tree = space.edit_tree
    if tree is None or not tree.is_editable:
        return None
    node = tree.nodes.active
    if (
        node is None
        or node.bl_idname not in types
        or node.image is None
        or not node.image.is_editable
    ):
        return None
    return node


def is_image_object(obj):
    """Return whether an object declares the AnyImage image capability."""
    get = getattr(obj, "get", None)
    return (
        getattr(obj, "type", None) == "MESH"
        and get is not None
        and bool(get("o_image_object", False))
    )


def object_image_texture(obj):
    """Find a connected texture in the current material, preferring a color image."""
    material = getattr(obj, "active_material", None)
    tree = getattr(material, "node_tree", None)
    if tree is None or not tree.is_editable:
        return None
    engine = bpy.context.scene.render.engine
    target = {"CYCLES": "CYCLES", "BLENDER_EEVEE_NEXT": "EEVEE"}.get(engine, "ALL")
    output = tree.get_output_node(target)
    if output is None:
        return None

    connected = set()
    visited = set()

    def trace(socket, groups):
        for link in socket.links:
            source = link.from_socket
            key = (source, groups)
            if not link.is_valid or link.is_muted or key in visited:
                continue
            visited.add(key)
            node = source.node
            if node.mute:
                inputs = [edge.from_socket for edge in node.internal_links if edge.to_socket == source]
            elif node.type == "GROUP" and node.node_tree:
                group_output = next((n for n in node.node_tree.nodes
                                     if n.type == "GROUP_OUTPUT" and n.is_active_output), None)
                if group_output:
                    for port in group_output.inputs:
                        if port.identifier == source.identifier:
                            trace(port, groups + (node,))
                continue
            elif node.type == "GROUP_INPUT" and groups:
                for port in groups[-1].inputs:
                    if port.identifier == source.identifier:
                        trace(port, groups[:-1])
                continue
            else:
                if node.type == "TEX_IMAGE" and not groups and node.image and node.image.is_editable:
                    connected.add(node)
                inputs = node.inputs
            for port in inputs:
                if port.enabled and port.is_linked:
                    trace(port, groups)

    for socket in output.inputs:
        trace(socket, ())
    candidates = [node for node in tree.nodes if node in connected]
    return next((node for node in candidates if "color" in node.image.name.casefold()),
                candidates[0] if candidates else None)


def image_edit_owner(context):
    """Resolve the editor's image owner without falling back across editors."""
    editor = getattr(getattr(context, "space_data", None), "type", None)
    if editor == "OUTLINER":
        return None
    if editor == "NODE_EDITOR":
        owner = active_texture_node(context)
    else:
        obj = getattr(context, "object", None)
        owner = obj if is_image_empty(obj) else object_image_texture(obj)
    if owner is not None and owner_image(owner).get(TEMPORARY_IMAGE_PREVIEW_PROPERTY):
        return None
    return owner


def editable_still_image(context):
    """Return the current image when it can be edited as a still."""
    image = owner_image(image_edit_owner(context))
    return image if is_static_image(image) else None


def replace_texture_image(node, result_image):
    """Commit one texture image transaction while preserving other users."""
    try:
        source_image = node.image
        original_timing = image_user_settings(node)
        original_auto_refresh = node.image_user.use_auto_refresh
        original_content = None
        try:
            if has_other_image_user(node):
                pack_image_result(result_image)
                final_image = result_image
            else:
                original_content = image_content_state(source_image)
                pack_image_result(result_image, source_image)
                final_image = source_image
            node.image = final_image
        except Exception:
            if original_content is not None:
                restore_image_content(source_image, original_content)
            node.image = source_image
            user = node.image_user
            (user.frame_start, user.frame_offset, user.frame_duration, user.use_cyclic) = original_timing
            user.use_auto_refresh = original_auto_refresh
            raise
        return final_image
    finally:
        if result_image.users == 0:
            bpy.data.images.remove(result_image)


def prepare_image_undo(image):
    """Pack unsaved pixels into the Undo step taken just before a job writes."""
    from pathlib import Path
    import tempfile
    from .hdr_image import save_image_exr

    if not image.is_dirty and image.source != "GENERATED":
        return
    state = image_content_state(image)
    try:
        if image.is_float and not image.colorspace_settings.is_data and state["colorspace"] != "Linear Rec.709":
            # Float buffers are scene-linear. The packed file must match the Image's color space.
            with tempfile.TemporaryDirectory(prefix="anyimage-undo-") as directory:
                path = Path(directory) / "source.exr"
                save_image_exr(image, path, state["colorspace"])
                data = path.read_bytes()
            image.pack(data=data, data_len=len(data))
        else:
            image.pack()
        if "FINISHED" not in bpy.ops.ed.undo_push(message="Before image edit"):
            raise RuntimeError("Unable to preserve the source image for Undo")
    finally:
        restore_image_content(image, state)


@dataclass
class ImageEditTarget:
    """Hold main-thread RNA identities for a single asynchronous image edit."""

    owner: object
    image: object
    tree: object = None
    node_identity: str = ""
    object_owner: object = None
    material: object = None
    material_slot: int = -1

    @classmethod
    def capture(cls, context):
        """Return the target and its current top-down RGBA from one pixel read."""
        owner = image_edit_owner(context)
        if owner is None:
            raise RuntimeError("Select an Image Empty or a shader texture with an image")
        image = owner_image(owner)
        if is_animated_image(image):
            raise RuntimeError("Only still images are supported")
        tree = None if is_image_empty(owner) else owner.id_data
        object_owner = None
        if tree is not None and getattr(getattr(context, "space_data", None), "type", None) != "NODE_EDITOR":
            object_owner = context.object
        material_slot = object_owner.active_material_index if object_owner is not None else -1
        material = object_owner.active_material if object_owner is not None else None
        identity = ""
        if tree is not None:
            identity = owner.get("anyimage_identity")
            if not identity:
                identity = uuid4().hex
                owner["anyimage_identity"] = identity
        key = (object_owner or owner).as_pointer()
        pixels = image_pixels(image)
        target = cls(owner, image, tree, identity, object_owner, material, material_slot)
        pending = _image_targets.get(key)
        if pending == target:
            target = pending
        else:
            _image_targets[key] = target
        return target, image_rgba(image, pixels)

    def validate_binding(self):
        """Reject a removed owner or a changed image assignment."""
        try:
            if self.tree is None:
                valid = is_image_empty(self.owner) and self.owner.data == self.image
            else:
                # 删除后的节点引用可能仍持有地址，只读取当前集合中节点的属性。
                valid = (
                    self.tree.is_editable
                    and self.image.is_editable
                    and any(
                        node == self.owner
                        and node.get("anyimage_identity") == self.node_identity
                        and node.image == self.image
                        for node in self.tree.nodes
                    )
                )
                if valid and self.object_owner is not None:
                    slots = self.object_owner.material_slots
                    valid = (
                        0 <= self.material_slot < len(slots)
                        and slots[self.material_slot].material == self.material
                        and self.material.node_tree == self.tree
                        and object_image_texture(self.object_owner) == self.owner
                    )
            if valid:
                return
        except ReferenceError:
            pass
        raise RuntimeError("The source image target is no longer available or has changed")

    def commit(self, result_image, *, prepare_undo=False):
        """Commit an owned, fully prepared image through the target transaction."""
        try:
            self.validate_binding()
            if prepare_undo:
                prepare_image_undo(self.image)
        except Exception:
            bpy.data.images.remove(result_image)
            raise
        if self.tree is None:
            image = replace_empty_image(self.owner, result_image)
        elif self.object_owner is not None and material_has_other_object_user(
            self.material,
            self.object_owner,
        ):
            image = self._commit_isolated_material(result_image)
        else:
            image = replace_texture_image(self.owner, result_image)
        # Pending edits of the same owner follow only our successful replacements.
        self.image = image
        return image

    def _commit_isolated_material(self, result_image):
        """Copy a shared material before committing this object's Color result."""
        slot = self.object_owner.material_slots[self.material_slot]
        original_link = slot.link
        material = None
        try:
            material = self.material.copy()
            node = material.node_tree.nodes[self.owner.name]
            pack_image_result(result_image)
            node.image = result_image
            if self.object_owner.data.users > 1:
                slot.link = "OBJECT"
            slot.material = material
        except Exception:
            slot.material = self.material
            slot.link = original_link
            if material is not None:
                bpy.data.materials.remove(material)
            bpy.data.images.remove(result_image)
            raise
        self.material = material
        self.tree = material.node_tree
        self.owner = node
        return result_image


def material_has_other_object_user(material, target):
    """Return whether another object uses the target object's material."""
    return any(
        obj != target
        and any(slot.material == material for slot in obj.material_slots)
        for obj in bpy.data.objects
    )
