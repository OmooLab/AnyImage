from unittest.mock import patch

import bpy
import numpy as np
import pytest

from anyimage.common import image as images
from anyimage.common import image_target as targets
from tests.support.image_texture import texture, texture_context, write_result


def test_target_uses_edit_tree_and_survives_renaming(texture, tmp_path):
    context = texture_context(texture, pin=True)
    target = targets.ImageEditTarget.capture(context)
    texture.name = "Renamed texture"
    bpy.data.materials["Texture material"].name = "Renamed material"
    other = texture.id_data.nodes.new("ShaderNodeTexImage")
    texture.id_data.nodes.active = other
    context.space_data.edit_tree = None
    write_result(tmp_path)
    target.apply(tmp_path / "foreground.png")
    assert tuple(texture.image.size) == (8, 6)
    assert other.image is None


@pytest.mark.parametrize("color_space,alpha_mode,filename,shared", [
    ("sRGB", "PREMUL", "foreground.png", True),
    ("AgX Base sRGB", "STRAIGHT", "upscale.png", False),
    ("Filmic sRGB", "STRAIGHT", "foreground.png", False),
    ("sRGB", "STRAIGHT", "upscale.png", True),
    ("AgX Base sRGB", "PREMUL", "foreground.png", True),
])
def test_image_actions_preserve_source_color_space_and_alpha(texture, tmp_path, color_space, alpha_mode, filename, shared):
    texture.image.colorspace_settings.name = color_space
    texture.image.alpha_mode = alpha_mode
    original = texture.image
    original_pixels = images.image_pixels(original)
    if shared:
        other = texture.id_data.nodes.new("ShaderNodeTexImage")
        other.image = original
    target = targets.ImageEditTarget.capture(texture_context(texture))
    write_result(tmp_path, filename)
    target.apply(tmp_path / filename)
    result = texture.image
    assert result.colorspace_settings.name == color_space
    assert result.alpha_mode == alpha_mode
    np.testing.assert_allclose(
        images.image_pixels(result).reshape(-1, 4),
        np.tile(np.array([128, 64, 32, 80]) / 255, (48, 1)),
        atol=1 / 255,
    )
    if shared:
        assert other.image == original
        assert original.alpha_mode == alpha_mode
        np.testing.assert_array_equal(images.image_pixels(original), original_pixels)


@pytest.mark.parametrize("invalid", ["world", "light", "compositor", "geometry", "missing_image", "other_node", "no_tree"])
def test_invalid_node_context_does_not_fall_back_to_empty(texture, invalid):
    context = texture_context(texture)
    context.object = bpy.data.objects.new("Fallback Empty", None)
    context.object.empty_display_type = "IMAGE"
    context.object.data = texture.image
    if invalid == "world":
        context.space_data.shader_type = "WORLD"
    elif invalid == "light":
        context.space_data.id = bpy.data.lights.new("Light", type="POINT")
    elif invalid in {"compositor", "geometry"}:
        context.space_data.tree_type = "CompositorNodeTree" if invalid == "compositor" else "GeometryNodeTree"
    elif invalid == "missing_image":
        texture.image = None
    elif invalid == "other_node":
        texture.id_data.nodes.active = texture.id_data.nodes.get("Principled BSDF")
    else:
        context.space_data.edit_tree = None
    assert targets.image_edit_owner(context) is None
    with pytest.raises(RuntimeError, match="Select"):
        targets.ImageEditTarget.capture(context)


@pytest.mark.parametrize("change", ["delete", "recreate", "rebind", "delete_material", "delete_image", "identity"])
def test_target_rejects_changed_identity_before_loading_result(texture, tmp_path, change):
    target = targets.ImageEditTarget.capture(texture_context(texture))
    tree = texture.id_data
    if change in {"delete", "recreate"}:
        name = texture.name
        tree.nodes.remove(texture)
        if change == "recreate":
            replacement = tree.nodes.new("ShaderNodeTexImage")
            replacement.name = name
            replacement.image = target.image
    elif change == "rebind":
        texture.image = bpy.data.images.new("Replacement", width=2, height=2)
    elif change == "delete_material":
        bpy.data.materials.remove(bpy.data.materials["Texture material"])
    elif change == "identity":
        # A reused RNA address must not make a replacement node the original target.
        texture["anyimage_identity"] = "replacement"
    else:
        bpy.data.images.remove(texture.image)
    count = len(bpy.data.images)
    with pytest.raises(RuntimeError, match="no longer available"):
        target.apply(tmp_path / "foreground.png")
    assert len(bpy.data.images) == count


@pytest.mark.parametrize("reference", ["sole", "fake_user", "editor", "same_tree", "other_material", "empty", "brush"])
def test_texture_commit_preserves_structure_and_isolates_users(texture, tmp_path, reference):
    original = texture.image
    original.colorspace_settings.name = "Non-Color"
    expected_source = images.image_pixels(original)
    source_packed = bytes(original.packed_file.data)
    original.use_fake_user = reference == "fake_user"
    target = targets.ImageEditTarget.capture(texture_context(texture))
    # Add users after capture to exercise changes while an AI job is pending.
    if reference == "same_tree":
        other = texture.id_data.nodes.new("ShaderNodeTexImage")
        other.image = original
    elif reference == "other_material":
        material = bpy.data.materials.new("Other material")
        material.use_nodes = True
        other = material.node_tree.nodes.new("ShaderNodeTexImage")
        other.image = original
    elif reference == "empty":
        other = bpy.data.objects.new("Other Empty", None)
        other.empty_display_type = "IMAGE"
        other.data = original
    elif reference == "brush":
        other = bpy.data.textures.new("Brush texture", type="IMAGE")
        other.image = original
    elif reference == "editor":
        area = bpy.context.screen.areas[0]
        area.type = "IMAGE_EDITOR"
        area.spaces.active.image = original
    shared = reference in {"same_tree", "other_material", "empty", "brush"}
    links = [(link.from_socket, link.to_socket) for link in texture.id_data.links]
    write_result(tmp_path)
    target.apply(tmp_path / "foreground.png")
    assert (texture.image == original) == (not shared)
    assert tuple(texture.image.size) == (8, 6)
    assert texture.image.colorspace_settings.name == "Non-Color"
    assert texture.image.alpha_mode == original.alpha_mode
    assert texture.image.packed_file is not None
    assert tuple(texture.location) == (-400, 100)
    assert (texture.interpolation, texture.extension, texture.projection) == ("Closest", "CLIP", "BOX")
    assert [(link.from_socket, link.to_socket) for link in texture.id_data.links] == links
    assert original.use_fake_user == (reference == "fake_user")
    if shared:
        assert (other.data if reference == "empty" else other.image) == original
        assert bytes(original.packed_file.data) == source_packed
        np.testing.assert_array_equal(images.image_pixels(original), expected_source)
    else:
        assert texture.image.name == "Texture.png"
        assert len(bpy.data.images) == 1
    expected = images.image_pixels(texture.image)
    path = str(tmp_path / "texture.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    reopened = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
    np.testing.assert_allclose(images.image_pixels(reopened.image), expected, atol=1 / 255)
    assert len(reopened.id_data.links) == len(links)




@pytest.mark.parametrize("source", ["MOVIE", "SEQUENCE"])
def test_target_rejects_animated_image(texture, source):
    texture.image.source = source
    with pytest.raises(RuntimeError, match="Only still images"):
        targets.ImageEditTarget.capture(texture_context(texture))


@pytest.mark.parametrize("shared", [False, True])
def test_failed_texture_assignment_restores_source(texture, tmp_path, shared):
    original = texture.image
    original.pixels.foreach_set(np.tile([0.1, 0.3, 0.7, 0.5], 12).astype(np.float32))
    packed = bytes(original.packed_file.data)
    pixels = images.image_pixels(original)
    result = images.load_image_edit_result(original, write_result(tmp_path))
    count = len(bpy.data.images) - 1

    class FailingTarget:
        failed = False

        def __getattr__(self, name):
            return getattr(texture, name)

        @property
        def image(self):
            return texture.image

        @image.setter
        def image(self, value):
            texture.image = value
            if not self.failed:
                self.failed = True
                raise RuntimeError("Assignment failed")

    with patch.object(targets, "has_other_image_user", return_value=shared):
        with pytest.raises(RuntimeError, match="Assignment failed"):
            targets.replace_texture_image(FailingTarget(), result)
    assert texture.image == original
    assert tuple(original.size) == (4, 3)
    assert bytes(original.packed_file.data) == packed
    np.testing.assert_array_equal(images.image_pixels(original), pixels)
    assert len(bpy.data.images) == count
