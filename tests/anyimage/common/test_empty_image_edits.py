from unittest.mock import patch
import bpy
import numpy as np
import pytest
from PIL import Image


from anyimage.common import image as images


@pytest.fixture
def source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Source.png", width=2, height=2, alpha=True)
    image.pixels.foreach_set(np.tile([0.2, 0.4, 0.6, 0.25], 4).astype(np.float32))
    image.pack()
    obj = create_empty("Source", image)
    yield obj
    bpy.ops.wm.read_factory_settings(use_empty=True)


def create_empty(name, image):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "IMAGE"
    obj.data = image
    bpy.context.collection.objects.link(obj)
    return obj


def edit_result(source):
    return images.create_image_edit_result(
        source.data, np.tile([0.8, 0.3, 0.1, 0.0], 12).astype(np.float32), (4, 3),
    )


@pytest.mark.parametrize("alpha_mode,shared,entry", [
    ("STRAIGHT", False, "pixels"),
    ("PREMUL", True, "foreground.png"),
    ("CHANNEL_PACKED", False, "upscale.png"),
    ("NONE", True, "pixels"),
])
def test_image_edit_replacement_preserves_alpha_mode(source, tmp_path, alpha_mode, shared, entry):
    original = source.data
    original.alpha_mode = alpha_mode
    if shared:
        other = create_empty("Other", original)
    if entry == "pixels":
        result = edit_result(source)
    else:
        Image.new("RGBA", (4, 3), (100, 150, 200, 128)).save(tmp_path / entry)
        result = images.load_image_edit_result(original, tmp_path / entry)
    assert result.alpha_mode == alpha_mode
    images.replace_empty_image(source, result)
    assert source.data.alpha_mode == alpha_mode
    assert (source.data == original) == (not shared)
    if shared:
        assert other.data == original and original.alpha_mode == alpha_mode


@pytest.mark.parametrize("sharing", ["visible", "hidden", "other_scene"])
def test_shared_edit_preserves_other_empty(source, sharing):
    original = source.data
    packed = bytes(original.packed_file.data)
    rgba = images.image_rgba(original)
    result = edit_result(source)
    # Create the second user after preparing the result, as during an async Job.
    other = create_empty("Other", original)
    other.hide_viewport = sharing == "hidden"
    if sharing == "other_scene":
        bpy.context.collection.objects.unlink(other)
        scene = bpy.data.scenes.new("Other scene")
        scene.collection.objects.link(other)
    other.empty_display_size = 7
    other.image_user.frame_start = 9
    assert images.has_other_image_empty(source)
    assert images.replace_empty_image(source, result) == result
    assert source.data == result
    assert result.name == "Source.png.001"
    assert other.data == original
    assert other.empty_display_size == 7
    assert other.image_user.frame_start == 9
    assert original.name == "Source.png"
    assert bytes(original.packed_file.data) == packed
    np.testing.assert_array_equal(images.image_rgba(original), rgba)


@pytest.mark.parametrize("reference", ["none", "fake_user", "material", "collections"])
def test_sole_edit_preserves_id_and_releases_result(source, reference, tmp_path):
    original = source.data
    pointer = original.as_pointer()
    original.use_fake_user = reference == "fake_user"
    if reference == "material":
        material = bpy.data.materials.new("Manual reference")
        material.use_nodes = True
        node = material.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = original
    if reference == "collections":
        collection = bpy.data.collections.new("Another collection")
        bpy.context.scene.collection.children.link(collection)
        collection.objects.link(source)
    count = len(bpy.data.images)
    result = edit_result(source)
    expected = images.image_rgba(result)
    assert not images.has_other_image_empty(source)
    final = images.replace_empty_image(source, result)
    assert final.as_pointer() == pointer == source.data.as_pointer()
    assert final.name == "Source.png"
    assert final.use_fake_user == (reference == "fake_user")
    assert len(bpy.data.images) == count
    if reference == "material":
        assert node.image == final
    np.testing.assert_allclose(images.image_rgba(final), expected, atol=1 / 255)
    path = str(tmp_path / "edited.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    reopened = bpy.data.objects["Source"].data
    assert reopened.name == "Source.png"
    np.testing.assert_allclose(images.image_rgba(reopened), expected, atol=1 / 255)


@pytest.mark.parametrize("outside", [False, True])
def test_frame_sharing_uses_surviving_objects(source, outside):
    original = source.data
    merged = create_empty("Merged", original)
    if outside:
        other = create_empty("Outside", original)
    assert images.has_other_image_empty(source, removed_objects=(merged,)) == outside
    result = edit_result(source)
    final = images.replace_empty_image(source, result, removed_objects=(merged,))
    bpy.data.objects.remove(merged, do_unlink=True)
    assert (final == original) == (not outside)
    if outside:
        assert other.data == original
        assert tuple(original.size) == (2, 2)


def test_failed_content_write_restores_source(source):
    original = source.data
    packed = bytes(original.packed_file.data)
    result = edit_result(source)
    restore = images.restore_image_content
    calls = 0

    def fail_once(image, state):
        nonlocal calls
        calls += 1
        restore(image, state)
        if calls == 1:
            raise RuntimeError("Write failed")

    with patch.object(images, "restore_image_content", side_effect=fail_once):
        with pytest.raises(RuntimeError, match="Write failed"):
            images.replace_empty_image(source, result)
    assert source.data == original
    assert tuple(original.size) == (2, 2)
    assert bytes(original.packed_file.data) == packed
    assert len(bpy.data.images) == 1


@pytest.mark.parametrize("floating", [False, True])
def test_failed_generated_commit_restores_unsaved_pixels(source, floating):
    original = bpy.data.images.new("Generated", width=3, height=2, alpha=True, float_buffer=floating)
    source.data = original
    original.pixels.foreach_set(np.tile([0.12, 0.24, 0.48, 0.5], 6).astype(np.float32))
    expected = images.image_pixels(original)
    result = edit_result(source)
    restore = images.restore_image_content
    calls = 0

    def fail_once(image, state):
        nonlocal calls
        calls += 1
        restore(image, state)
        if calls == 1:
            raise RuntimeError("Write failed")

    with patch.object(images, "restore_image_content", side_effect=fail_once):
        with pytest.raises(RuntimeError, match="Write failed"):
            images.replace_empty_image(source, result)
    assert original.source == "GENERATED"
    assert original.is_float == floating
    assert original.packed_file is None
    assert tuple(original.size) == (3, 2)
    np.testing.assert_array_equal(images.image_pixels(original), expected)


def test_failed_preparation_releases_result(source):
    result = edit_result(source)
    count = len(bpy.data.images) - 1
    with patch.object(images, "empty_display_alignment", side_effect=ValueError("Invalid bounds")):
        with pytest.raises(ValueError, match="Invalid bounds"):
            images.replace_empty_image(source, result, placement_bounds=(0, 0, 1, 1))
    assert len(bpy.data.images) == count
    assert tuple(source.data.size) == (2, 2)
