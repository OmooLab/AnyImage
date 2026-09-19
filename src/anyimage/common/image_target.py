"""Resolve and commit AI image edits for Empty objects and texture nodes."""

from dataclasses import dataclass
from uuid import uuid4

import bpy

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


def image_edit_owner(context):
    """Resolve the editor's image owner without falling back across editors."""
    if getattr(getattr(context, "space_data", None), "type", None) == "NODE_EDITOR":
        return active_texture_node(context)
    owner = getattr(context, "object", None)
    return owner if is_image_empty(owner) else None


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

    @classmethod
    def capture(cls, context):
        owner = image_edit_owner(context)
        if owner is None:
            raise RuntimeError("Select an Image Empty or a material Image Texture")
        image = owner_image(owner)
        if is_animated_image(image):
            raise RuntimeError("Only still images are supported")
        tree = None if is_image_empty(owner) else owner.id_data
        identity = ""
        if tree is not None:
            identity = owner.get("anyimage_identity")
            if not identity:
                identity = uuid4().hex
                owner["anyimage_identity"] = identity
        return cls(
            owner, image, tree, identity,
        )

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
        return replace_texture_image(self.owner, result_image)
