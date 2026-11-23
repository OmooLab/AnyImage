import bpy
import numpy as np
import pytest

from anyimage.common import color_reference as reference_cache
from anyimage.common.image import image_rgba
from tests.support.color_reference import create_clipboard_image, registered_color_reference


def test_set_reference_previews_current_image_and_colors(registered_color_reference):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from anyimage.panels import ColorMatchPanel
    from tests.support.color_reference import create_image_empty

    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = create_clipboard_image("Reference", np.full((3, 4, 4), (.8, .2, .1, .5)))
    owner = create_image_empty("Selected reference", image)
    bpy.context.view_layer.objects.active = owner
    assert bpy.ops.anyimage.set_color_reference() == {"FINISHED"}
    assert bpy.context.scene.anyimage_settings.color_reference == image
    layout = Mock(spec_set=["label", "template_icon", "row"])
    row = layout.row.return_value
    ColorMatchPanel.draw(SimpleNamespace(layout=layout), bpy.context)
    prepared = reference_cache.get_color_reference(image)
    layout.template_icon.assert_called_once_with(icon_value=prepared.icon_id, scale=6.0)
    cell = row.row.return_value
    settings = bpy.context.scene.anyimage_settings
    cell.prop.assert_called_once_with(settings, "reference_swatch_0", text="")
    assert cell.scale_x == 1.0
    np.testing.assert_allclose(settings.reference_swatch_0, prepared.transfer.colors[0])


def test_setting_reference_does_not_add_an_undo_step(registered_color_reference):
    from tests.support.color_reference import create_image_empty

    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = create_clipboard_image("Reference", np.ones((2, 2, 4)))
    owner = create_image_empty("Movable reference", image)
    bpy.context.view_layer.objects.active = owner
    bpy.context.preferences.edit.use_global_undo = True
    bpy.ops.ed.undo_push(message="Before move")
    owner.location.x = 2
    bpy.ops.ed.undo_push(message="Move")
    assert bpy.ops.anyimage.set_color_reference() == {"FINISHED"}
    assert bpy.ops.ed.undo() == {"FINISHED"}
    assert bpy.data.objects["Movable reference"].location.x == 0


@pytest.mark.parametrize("fake_user", [False, True])
def test_scene_reference_survives_save_and_reopen(tmp_path, registered_color_reference, fake_user):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Persistent reference", np.full((2, 2, 4), (0.4, 0.3, 0.2, 1.0)))
    reference.use_fake_user = fake_user
    bpy.context.scene.anyimage_settings.color_reference = reference
    path = tmp_path / "color-reference.blend"

    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))

    assert bpy.context.scene.anyimage_settings.color_reference == bpy.data.images["Persistent reference"]
    assert bpy.data.images["Persistent reference"].use_fake_user == fake_user


def test_undo_redo_rebuilds_selected_preview_from_restored_pixels(registered_color_reference):
    from anyimage.common.image import image_content_state, restore_image_content

    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Undo reference preview", np.full((4, 4, 4), (.7, .2, .1, 1)))
    bpy.context.scene.anyimage_settings.color_reference = reference
    result = create_clipboard_image("Edited reference", np.full((6, 8, 4), (.1, .7, .2, .25)))
    bpy.context.preferences.edit.use_global_undo = True
    bpy.ops.ed.undo_push(message="Before reference edit")
    restore_image_content(reference, image_content_state(result))
    bpy.ops.ed.undo_push(message="After reference edit")
    for operation, alpha in ((bpy.ops.ed.undo, 1.0), (bpy.ops.ed.redo, .25)):
        assert operation() == {"FINISHED"}
        current = bpy.context.scene.anyimage_settings.color_reference
        assert not reference_cache._references
        prepared = reference_cache.get_color_reference(current)
        np.testing.assert_allclose(image_rgba(prepared.image)[..., 3], alpha, atol=1/255)
        preview = reference_cache._previews[str(current.session_uid)]
        np.testing.assert_allclose(np.asarray(preview.image_pixels_float).reshape(-1, 4)[:, 3], alpha, atol=1/255)
