import bpy
import numpy as np
import pytest
from anyimage import properties
from anyimage.common import color_reference as reference_cache
from anyimage.common.image import image_rgba
from anyimage.common.color_space import srgb_to_linear_rgb
from tests.support.color_reference import create_rgba_image, create_clipboard_image, create_image_empty, registered_color_reference, isolate_reference_cache


def test_scene_reference_defaults_replaces_and_clears(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first = create_clipboard_image("First", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    second = create_clipboard_image("Second", np.full((2, 2, 4), (0.6, 0.2, 0.1, 1.0)))

    assert bpy.context.scene.anyimage_settings.color_reference is None
    bpy.context.scene.anyimage_settings.color_reference = first
    settings = bpy.context.scene.anyimage_settings
    assert settings.color_reference == first
    assert settings.color_reference_palette_count == 1
    np.testing.assert_allclose(
        settings.color_reference_palette_0,
        srgb_to_linear_rgb((0.2, 0.3, 0.4)),
        atol=1 / 255,
    )
    assert settings.color_reference_palette_weight_0 == 1.0
    for name in properties.COLOR_REFERENCE_PALETTE_PROPERTIES[1:]:
        np.testing.assert_array_equal(getattr(settings, name), (0.0, 0.0, 0.0))
    bpy.context.scene.anyimage_settings.color_reference = second
    assert settings.color_reference == second
    bpy.context.scene.anyimage_settings.color_reference = None
    assert settings.color_reference is None
    assert settings.color_reference_palette_count == 0



def test_reference_edit_refreshes_detached_preview_and_palette_without_reselection(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rgba = np.full((4, 4, 4), (0.7, 0.2, 0.1, 1.0), dtype=np.float32)
    reference = create_clipboard_image("Reference", rgba)
    bpy.context.scene.anyimage_settings.color_reference = reference
    icon = reference_cache.color_reference_preview_icon(reference)
    items = properties.color_reference_items(None, None)
    assert next(item[3] for item in items if item[1] == reference.name) == icon
    reference.preview_ensure().reload()
    assert reference_cache.color_reference_preview_icon(reference) == icon
    from anyimage.common.image import image_content_state, restore_image_content
    result = create_clipboard_image("Edited reference", np.full((6, 8, 4), (0.1, 0.7, 0.2, .25)))
    restore_image_content(reference, image_content_state(result))
    assert str(reference.as_pointer()) in reference_cache._previews
    refreshed = reference_cache.get_color_reference(reference)
    np.testing.assert_allclose(image_rgba(refreshed.image)[..., :3], np.broadcast_to((.1, .7, .2), (6, 8, 3)), atol=1/255)
    np.testing.assert_allclose(image_rgba(refreshed.image)[..., 3], .25, atol=1/255)
    preview = reference_cache._previews[str(reference.as_pointer())]
    np.testing.assert_allclose(np.asarray(preview.image_pixels_float).reshape(-1, 4)[:, 3], .25, atol=1/255)
    settings = bpy.context.scene.anyimage_settings
    np.testing.assert_allclose(settings.color_reference_palette_0, srgb_to_linear_rgb((.1, .7, .2)), atol=.005)



def test_color_reference_gallery_selects_only_candidates(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    create_rgba_image("Reference_depth.exr", np.full((2, 2, 4), (0.6, 0.2, 0.1, 1.0)))
    settings = bpy.context.scene.anyimage_settings

    items = properties.color_reference_items(settings, bpy.context)

    assert [item[1] for item in items] == ["None", "Reference"]
    properties.set_color_reference_choice(settings, items[1][4])
    assert settings.color_reference == reference
    assert properties.get_color_reference_choice(settings) == items[1][4]
    properties.set_color_reference_choice(settings, 0)
    assert settings.color_reference is None
    assert properties.get_color_reference_choice(settings) == 0



def test_scene_reference_survives_save_and_reopen(tmp_path, registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Persistent reference", np.full((2, 2, 4), (0.4, 0.3, 0.2, 1.0)))
    reference.use_fake_user = True
    bpy.context.scene.anyimage_settings.color_reference = reference
    path = tmp_path / "color-reference.blend"

    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))

    assert bpy.context.scene.anyimage_settings.color_reference == bpy.data.images["Persistent reference"]



def test_reference_reload_and_lifecycle_invalidate_cache(tmp_path, registered_color_reference):
    from PIL import Image

    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = tmp_path / "reference.png"
    Image.new("RGB", (4, 4), "red").save(path)
    reference = bpy.data.images.load(str(path))
    create_image_empty("Reference", reference)
    bpy.context.scene.anyimage_settings.color_reference = reference
    first = reference_cache.get_color_reference(reference)
    Image.new("RGB", (4, 4), "blue").save(path)
    reference.reload()
    second = reference_cache.get_color_reference(reference, refresh=True)
    assert second is not first
    assert image_rgba(second.image)[0, 0, 2] > .9
    properties.register_color_references()
    try:
        for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
            assert properties.restore_color_references in handlers
            properties.restore_color_references(None)
            current = reference_cache.get_color_reference(reference)
            assert current is not second
            assert str(reference.as_pointer()) in reference_cache._previews
            second = current
    finally:
        properties.unregister_color_references()
    assert reference_cache.color_reference_preview_icon(reference) == 0



def test_undo_redo_rebuilds_selected_preview_from_restored_pixels(registered_color_reference):
    from anyimage.common.image import image_content_state, restore_image_content

    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Undo reference preview", np.full((4, 4, 4), (.7, .2, .1, 1)))
    bpy.context.scene.anyimage_settings.color_reference = reference
    result = create_clipboard_image("Edited reference", np.full((6, 8, 4), (.1, .7, .2, .25)))
    properties.register_color_references()
    try:
        bpy.context.preferences.edit.use_global_undo = True
        bpy.ops.ed.undo_push(message="Before reference edit")
        restore_image_content(reference, image_content_state(result))
        bpy.ops.ed.undo_push(message="After reference edit")
        for operation, alpha in ((bpy.ops.ed.undo, 1.0), (bpy.ops.ed.redo, .25)):
            assert operation() == {"FINISHED"}
            current = bpy.context.scene.anyimage_settings.color_reference
            prepared = reference_cache.get_color_reference(current)
            np.testing.assert_allclose(image_rgba(prepared.image)[..., 3], alpha, atol=1/255)
            preview = reference_cache._previews[str(current.as_pointer())]
            np.testing.assert_allclose(np.asarray(preview.image_pixels_float).reshape(-1, 4)[:, 3], alpha, atol=1/255)
            items = properties.color_reference_items(None, None)
            assert next(item[3] for item in items if item[1] == current.name) == preview.icon_id
    finally:
        properties.unregister_color_references()



def test_failed_reference_preparation_does_not_keep_old_pixels(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    settings = bpy.context.scene.anyimage_settings
    settings.color_reference = reference
    reference.pixels.foreach_set(np.zeros(64, dtype=np.float32))
    reference.update()
    properties.update_color_reference_palette(settings, None)
    assert settings.color_reference_palette_count == 0
    with pytest.raises(ValueError, match="no visible"):
        reference_cache.get_color_reference(reference)
    assert reference_cache.color_reference_preview_icon(reference) == 0



@pytest.mark.parametrize("shared", [False, True])
def test_scene_clear_preserves_other_scene_reference(shared, registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first = create_clipboard_image("Scene A reference", np.full((4, 4, 4), (.7, .2, .1, 1)))
    second = first if shared else create_clipboard_image("Scene B reference", np.full((4, 4, 4), (.1, .2, .7, 1)))
    settings = bpy.context.scene.anyimage_settings
    settings.color_reference = first
    prepared = reference_cache.get_color_reference(first)
    icon = reference_cache.color_reference_preview_icon(first)
    other = bpy.data.scenes.new("Scene B")
    other.anyimage_settings.color_reference = second
    other.anyimage_settings.color_reference = None
    assert settings.color_reference == first
    assert reference_cache.get_color_reference(first) is prepared
    assert reference_cache.color_reference_preview_icon(first) == icon
    assert settings.color_reference_palette_count == len(prepared.colors)
    if not shared:
        assert reference_cache.color_reference_preview_icon(second) == 0
    bpy.data.scenes.remove(other)


def test_replaced_references_release_palette_data_and_keep_candidate_icons(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    settings = bpy.context.scene.anyimage_settings
    previous = None
    for index in range(4):
        image = create_clipboard_image(f"Reference {index}", np.full((256, 256, 4), (.2 + index * .1, .3, .4, 1)))
        settings.color_reference = image
        prepared = reference_cache.get_color_reference(image)
        assert not hasattr(prepared, "rgba")
        assert len(prepared.content_digest) == 32
        assert len(reference_cache._references) == 1
        if previous is not None:
            assert str(previous.as_pointer()) in reference_cache._previews
        previous = image
    settings.color_reference = None
    assert not reference_cache._references


def test_gallery_preserves_edited_alpha_before_selection(registered_color_reference):
    from unittest.mock import patch
    from anyimage.common.image import image_content_state, restore_image_content

    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Unselected reference", np.full((4, 4, 4), (.7, .2, .1, 1)))
    properties.color_reference_items(None, None)
    edited = create_clipboard_image("Alpha result", np.full((4, 4, 4), (.7, .2, .1, .25)))
    restore_image_content(reference, image_content_state(edited))
    bpy.data.images.remove(edited)
    with patch.object(reference_cache, "extract_reference_palette", side_effect=AssertionError("Gallery must only prepare previews")):
        items = properties.color_reference_items(None, None)
        assert properties.color_reference_items(None, None) is items
    key = str(reference.as_pointer())
    preview = reference_cache._previews[key]
    assert next(item[3] for item in items if item[1] == reference.name) == preview.icon_id
    for prefix in ("image", "icon"):
        pixels = np.asarray(getattr(preview, f"{prefix}_pixels_float")).reshape(-1, 4)
        np.testing.assert_allclose(pixels[:, 3], .25, atol=1/255)
    assert not reference_cache._references
    bpy.context.scene.anyimage_settings.color_reference = reference
    pixels = np.asarray(reference_cache._previews[key].icon_pixels_float).reshape(-1, 4)
    np.testing.assert_allclose(pixels[:, 3], .25, atol=1/255)
    bpy.context.scene.anyimage_settings.color_reference = None
    bpy.data.images.remove(reference)
    properties.color_reference_items(None, None)
    assert key not in reference_cache._previews
