"""Resolve and commit AI image edits for image owners."""

from dataclasses import dataclass
from uuid import uuid4

import bpy

from .material import (
    DEPTH_MATERIAL_NODE_GROUP_NAME,
    IMAGE_MATERIAL_NODE_GROUP_NAME,
    SHADELESS_NODE_GROUP_NAME,
)
from .image import (
    image_content_state,
    image_user_settings,
    is_animated_image,
    is_image_empty,
    load_image_edit_result,
    prepare_image_input,
    replace_empty_image,
    restore_image_content,
)


def active_texture_node(context):
    """Return the editable image texture in the current material edit tree."""
    space = getattr(context, "space_data", None)
    if (
        getattr(space, "type", None) != "NODE_EDITOR"
        or getattr(space, "tree_type", None) != "ShaderNodeTree"
        or getattr(space, "shader_type", None) != "OBJECT"
        or not isinstance(getattr(space, "id", None), bpy.types.Material)
    ):
        return None
    tree = space.edit_tree
    if tree is None or not tree.is_editable:
        return None
    node = tree.nodes.active
    if (
        node is None
        or node.bl_idname != "ShaderNodeTexImage"
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


def _linked_source(socket):
    links = tuple(getattr(socket, "links", ()))
    return links[0].from_node if len(links) == 1 else None


def _image_layer_texture(node):
    if node is None or node.bl_idname != "ShaderNodeGroup":
        return None
    if getattr(getattr(node, "node_tree", None), "name", "") not in {
        IMAGE_MATERIAL_NODE_GROUP_NAME,
        DEPTH_MATERIAL_NODE_GROUP_NAME,
    }:
        return None
    source = _linked_source(node.inputs.get("Color"))
    return source if getattr(source, "bl_idname", None) == "ShaderNodeTexImage" else None


def _material_color_source(shader):
    if shader is None:
        return None
    if shader.bl_idname == "ShaderNodeBsdfPrincipled":
        return _image_layer_texture(_linked_source(shader.inputs.get("Base Color")))
    if shader.bl_idname == "ShaderNodeEmission":
        source = _linked_source(shader.inputs.get("Color"))
        return source if getattr(source, "bl_idname", None) == "ShaderNodeTexImage" else None
    if (
        shader.bl_idname == "ShaderNodeGroup"
        and getattr(getattr(shader, "node_tree", None), "name", "")
        == SHADELESS_NODE_GROUP_NAME
    ):
        source = _linked_source(shader.inputs.get("Color"))
        if getattr(source, "bl_idname", None) == "ShaderNodeTexImage":
            return source
        return _image_layer_texture(source)
    return None


def object_color_texture(obj):
    """Resolve the Color Image Texture from a generated image object's material."""
    if not is_image_object(obj):
        return None
    material = getattr(obj, "active_material", None)
    tree = getattr(material, "node_tree", None)
    if tree is None or not tree.is_editable:
        return None
    outputs = [
        node
        for node in tree.nodes
        if node.bl_idname == "ShaderNodeOutputMaterial"
        and node.is_active_output
        and node.inputs["Surface"].is_linked
    ]
    if len(outputs) != 1:
        return None
    node = _material_color_source(_linked_source(outputs[0].inputs["Surface"]))
    if (
        node is None
        or node.id_data != tree
        or node.image is None
        or not node.image.is_editable
    ):
        return None
    return node


def image_edit_owner(context):
    """Resolve the editor's image owner without falling back across editors."""
    if getattr(getattr(context, "space_data", None), "type", None) == "NODE_EDITOR":
        return active_texture_node(context)
    owner = getattr(context, "object", None)
    if is_image_empty(owner):
        return owner
    return object_color_texture(owner)


def owner_image(owner):
    """Return the Image assigned to an image Empty or texture node."""
    return owner.data if is_image_empty(owner) else owner.image


def has_other_image_user(owner):
    """Check actual Image references, excluding editor display and Fake User."""
    tree = None if is_image_empty(owner) else owner.id_data
    image = owner_image(owner)
    for user in bpy.data.user_map(subset={image})[image]:
        if isinstance(user, bpy.types.Screen):
            continue
        if user == owner:
            continue
        if tree is not None and (user == tree or getattr(user, "node_tree", None) == tree):
            if any(
                other != owner and getattr(other, "image", None) == image
                for other in tree.nodes
            ):
                return True
        else:
            return True
    return False


def replace_texture_image(node, result_image):
    """Commit one texture image transaction while preserving other users."""
    try:
        source_image = node.image
        original_timing = image_user_settings(node)
        original_auto_refresh = node.image_user.use_auto_refresh
        original_content = None
        try:
            if has_other_image_user(node):
                final_image = result_image
            else:
                result_content = image_content_state(result_image)
                original_content = image_content_state(source_image)
                restore_image_content(source_image, result_content)
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
        owner = image_edit_owner(context)
        if owner is None:
            raise RuntimeError("Select an Image Empty or a material Image Texture")
        image = owner_image(owner)
        if is_animated_image(image):
            raise RuntimeError("Only still images are supported")
        tree = None if is_image_empty(owner) else owner.id_data
        object_owner = getattr(context, "object", None)
        if not is_image_object(object_owner) or object_color_texture(object_owner) != owner:
            object_owner = None
        material = getattr(object_owner, "active_material", None)
        material_slot = (
            int(object_owner.active_material_index)
            if object_owner is not None
            else -1
        )
        identity = ""
        if tree is not None:
            identity = owner.get("anyimage_identity")
            if not identity:
                identity = uuid4().hex
                owner["anyimage_identity"] = identity
        return cls(owner, image, tree, identity, object_owner, material, material_slot)

    def validate(self):
        """Reject a removed owner or a changed image assignment."""
        try:
            if self.tree is None:
                valid = is_image_empty(self.owner) and self.owner.data == self.image
            else:
                valid = (
                    self.tree.is_editable
                    and self.image.is_editable
                    and self.tree.nodes.get(self.owner.name) == self.owner
                    and self.owner.image == self.image
                    and self.owner.get("anyimage_identity") == self.node_identity
                )
                if valid and self.object_owner is not None:
                    slots = self.object_owner.material_slots
                    valid = (
                        is_image_object(self.object_owner)
                        and 0 <= self.material_slot < len(slots)
                        and slots[self.material_slot].material == self.material
                        and self.material.node_tree == self.tree
                        and object_color_texture(self.object_owner) == self.owner
                    )
            if valid:
                return
        except ReferenceError:
            pass
        raise RuntimeError("The source image target is no longer available or has changed")

    def prepare(self, context):
        self.validate()
        return prepare_image_input(self.image, context.scene)

    def apply(self, output_path):
        self.validate()
        result_image = load_image_edit_result(self.image, output_path)
        return self.commit(result_image)

    def commit(self, result_image, *, isolate_shared=False):
        """Commit an owned, fully prepared image through the target transaction."""
        try:
            self.validate()
        except Exception:
            bpy.data.images.remove(result_image)
            raise
        if self.tree is None:
            if isolate_shared:
                return replace_empty_image(
                    self.owner, result_image, isolate_image=has_other_image_user(self.owner),
                )
            return replace_empty_image(self.owner, result_image)
        if self.object_owner is not None and _material_has_other_object_user(
            self.material,
            self.object_owner,
        ):
            return self._commit_isolated_material(result_image)
        return replace_texture_image(self.owner, result_image)

    def _commit_isolated_material(self, result_image):
        """Copy a shared material before committing this object's Color result."""
        slot = self.object_owner.material_slots[self.material_slot]
        source_material = self.material
        copied_material = source_material.copy()
        try:
            slot.material = copied_material
            copied_node = next(
                (
                    node
                    for node in copied_material.node_tree.nodes
                    if node.get("anyimage_identity") == self.node_identity
                ),
                None,
            )
            if copied_node is None or copied_node.image != self.image:
                raise RuntimeError("Unable to isolate the object image material")
            return replace_texture_image(copied_node, result_image)
        except Exception:
            slot.material = source_material
            if copied_material.users == 0:
                bpy.data.materials.remove(copied_material)
            raise


def _material_has_other_object_user(material, target):
    return any(
        obj != target
        and any(slot.material == material for slot in obj.material_slots)
        for obj in bpy.data.objects
    )
