"""Verify cache identity against edits to real Blender images."""

from io import BytesIO
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import image as images
from anyimage.common.selection import SelectionMask
from anyimage.operators.clipboard_image import actions
from anyimage.operators.mask_tool import EditImageAlpha


@pytest.fixture
def clipboard():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    stream = BytesIO()
    Image.fromarray(np.array([[[100, 150, 200, 255], [50, 80, 120, 0]]], np.uint8)).save(stream, format="PNG")
    yield stream.getvalue()
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("edit", ["paint", "packed", "hidden_rgb", "size", "space", "alpha", "unreadable"])
def test_changed_cache_is_skipped_without_modifying_candidate(clipboard, edit, monkeypatch):
    original, reused = actions.acquire_packed_image(clipboard, ".png")
    expected = images.image_pixels(original)
    assert not reused
    assert actions.acquire_packed_image(clipboard, ".png") == (original, True)
    if edit in {"paint", "packed"}:
        original.pixels[0] = 1
        if edit == "packed":
            original.pack()
    elif edit == "hidden_rgb":
        original.pixels[4] = 1
    elif edit == "size":
        original.scale(4, 2)
    elif edit == "space":
        original.colorspace_settings.name = "Non-Color"
    elif edit == "alpha":
        original.alpha_mode = "PREMUL"
    else:
        read = actions._clipboard_content_hash
        def fail_candidate(image):
            if image == original:
                raise RuntimeError("Unreadable candidate")
            return read(image)
        monkeypatch.setattr(actions, "_clipboard_content_hash", fail_candidate)
    state = images.image_content_state(original)
    current_pixels = original.pixels[:]
    replacement, reused = actions.acquire_packed_image(clipboard, ".png")
    assert replacement != original and not reused
    np.testing.assert_array_equal(images.image_pixels(replacement), expected)
    assert (original.colorspace_settings.name, original.alpha_mode) == (state["colorspace"], state["alpha_mode"])
    assert bytes(original.packed_file.data) == state["packed"]
    np.testing.assert_array_equal(original.pixels[:], current_pixels)


@pytest.mark.parametrize("shared", [False, True])
def test_mask_edit_then_paste_preserves_original_clipboard_content(clipboard, shared):
    original, _ = actions.acquire_packed_image(clipboard, ".png")
    expected = images.image_pixels(original)
    owner = bpy.data.objects.new("Clipboard Empty", None)
    owner.empty_display_type = "IMAGE"
    owner.data = original
    bpy.context.collection.objects.link(owner)
    if shared:
        other = owner.copy()
        bpy.context.collection.objects.link(other)
    mask = SelectionMask(np.full((1, 2), .5, np.float32), (0, 0, 2, 1))
    assert EditImageAlpha._apply_mask(SimpleNamespace(mode="SUBTRACT"), bpy.context, owner, mask) == {"FINISHED"}
    edited = owner.data
    edited_pixels = images.image_pixels(edited)
    assert edited.packed_file
    assert (edited == original) == (not shared)
    pasted, reused = actions.acquire_packed_image(clipboard, ".png")
    assert reused == shared
    assert pasted != edited
    np.testing.assert_array_equal(images.image_pixels(pasted), expected)
    np.testing.assert_array_equal(images.image_pixels(edited), edited_pixels)


def test_painted_clipboard_plane_keeps_reference_node_and_brush_cache(clipboard, monkeypatch):
    original, _ = actions.acquire_packed_image(clipboard, ".png")
    expected = images.image_pixels(original)
    monkeypatch.setattr(actions, "_place_in_view", lambda *_: None)
    monkeypatch.setattr(actions, "_select_only", lambda *_: None)
    obj = actions.add_image_plane(bpy.context, original, shadeless=False)
    color = next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type == "TEX_IMAGE")
    assert color != original and actions.CLIPBOARD_HASH_PROPERTY not in color
    assert actions.CLIPBOARD_CONTENT_PROPERTY not in color
    color.pixels[0] = 1
    color.pack()
    for _ in range(3):
        pasted, reused = actions.acquire_packed_image(clipboard, ".png")
        assert pasted == original and reused
        np.testing.assert_array_equal(images.image_pixels(pasted), expected)


def test_failed_clipboard_plane_placement_releases_created_data(clipboard, monkeypatch):
    original, _ = actions.acquire_packed_image(clipboard, ".png")
    before = {name: set(getattr(bpy.data, name)) for name in ("images", "objects", "meshes", "materials")}
    def fail(*_):
        raise RuntimeError("Placement failed")
    monkeypatch.setattr(actions, "_place_in_view", fail)
    with pytest.raises(RuntimeError, match="Placement failed"):
        actions.add_image_plane(bpy.context, original)
    for name, items in before.items():
        assert set(getattr(bpy.data, name)) == items
