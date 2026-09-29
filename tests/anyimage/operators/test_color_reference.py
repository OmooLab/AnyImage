from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest

from anyimage import properties
from anyimage.common import material as material_data
from anyimage.common import color_reference as reference_cache
from anyimage.common.color_match import prepare_color_reference, build_color_match, apply_color_match
from anyimage.common.color_space import image_rgba_to_linear, linear_rgba_to_image, srgb_to_linear_rgb
from anyimage.common.image import image_rgba, is_color_reference_candidate
from anyimage.common.image_target import ImageEditTarget
from anyimage.operators import color_reference
from anyimage.operators.color_reference import (
    MatchColorReference,
    current_color_reference,
)


def _image(name, rgba, *, floating=False):
    rgba = np.asarray(rgba, dtype=np.float32)
    image = bpy.data.images.new(
        name,
        width=rgba.shape[1],
        height=rgba.shape[0],
        alpha=True,
        float_buffer=floating,
    )
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    image.pack()
    image.update()
    return image


def _empty(name, image):
    owner = bpy.data.objects.new(name, None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.scene.collection.objects.link(owner)
    return owner


def _image_object(name, image):
    material = material_data.create_image_material(SimpleNamespace(name=name), image)
    mesh = bpy.data.meshes.new(name)
    mesh.materials.append(material)
    owner = bpy.data.objects.new(name, mesh)
    owner["o_image_object"] = True
    bpy.context.scene.collection.objects.link(owner)
    return owner, material


def _context(owner, reference=None):
    return SimpleNamespace(
        space_data=SimpleNamespace(type="VIEW_3D"),
        object=owner,
        scene=SimpleNamespace(
            anyimage_settings=SimpleNamespace(color_reference=reference),
        ),
    )


def _execute(operator_type, context):
    return operator_type.execute(
        SimpleNamespace(report=lambda *_args: None),
        context,
    )


def _modal_operator():
    reports = []
    operator = SimpleNamespace(
        report=lambda level, message: reports.append((level, message)),
        _MOUSE_SCALE=MatchColorReference._MOUSE_SCALE,
        _PRECISE_SCALE=MatchColorReference._PRECISE_SCALE,
        _PREVIEW_INTERVAL=MatchColorReference._PREVIEW_INTERVAL,
    )
    for name in (
        "_preview_pixels",
        "_commit",
        "_add_preview_handler",
        "_tag_redraw",
        "_finish",
    ):
        setattr(operator, name, MethodType(getattr(MatchColorReference, name), operator))
    return operator, reports


def _modal_context(owner, reference):
    context = _context(owner, reference)
    context.area = SimpleNamespace(tag_redraw=Mock())
    context.window = None
    context.window_manager = SimpleNamespace(
        modal_handler_add=Mock(), event_timer_add=Mock(return_value=object()), event_timer_remove=Mock(),
    )
    return context


def _event(event_type, *, x=100, y=100, value="PRESS", shift=False):
    return SimpleNamespace(
        type=event_type,
        value=value,
        mouse_x=x,
        mouse_y=y,
        shift=shift,
    )


@pytest.fixture(autouse=True)
def isolate_reference_cache():
    reference_cache.clear_color_references()
    yield
    reference_cache.clear_color_references()


@pytest.fixture
def registered_color_reference():
    try:
        bpy.utils.register_class(properties.AnyImageSettings)
        registered_settings = True
    except (RuntimeError, ValueError):
        registered_settings = False
    added_scene_property = not hasattr(bpy.types.Scene, "anyimage_settings")
    if added_scene_property:
        bpy.types.Scene.anyimage_settings = bpy.props.PointerProperty(
            type=properties.AnyImageSettings,
        )
    registered_operators = []
    for operator in (MatchColorReference,):
        try:
            bpy.utils.register_class(operator)
            registered_operators.append(operator)
        except (RuntimeError, ValueError):
            pass
    yield
    for operator in reversed(registered_operators):
        bpy.utils.unregister_class(operator)
    if added_scene_property:
        del bpy.types.Scene.anyimage_settings
    if registered_settings:
        bpy.utils.unregister_class(properties.AnyImageSettings)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Reference", True),
        ("Reference.PNG", True),
        ("Subject_normal", False),
        ("Subject_DEPTH", False),
        ("Subject_color", False),
        ("Subject_normal.001", False),
        ("Subject_depth.exr.002", False),
        ("Subject_color.png.003", False),
    ],
)
def test_color_reference_candidate_filters_generated_image_names(name, expected):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = _image(name, np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    assert is_color_reference_candidate(image) is expected


def test_color_reference_candidate_rejects_animated_images():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = _image("Sequence", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    image.source = "SEQUENCE"
    assert not is_color_reference_candidate(image)


def test_scene_reference_defaults_replaces_and_clears(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first = _image("First", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    second = _image("Second", np.full((2, 2, 4), (0.6, 0.2, 0.1, 1.0)))

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


def test_selection_prepares_reference_and_match_only_analyzes_target(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference_cache.clear_color_references()
    reference = _image("Cached reference", np.full((8, 8, 4), (0.7, 0.2, 0.1, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.1, 0.2, 0.6, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    with patch.object(reference_cache, "image_rgba", wraps=reference_cache.image_rgba) as read_reference:
        bpy.context.scene.anyimage_settings.color_reference = reference
        assert read_reference.call_count == 1
        for _ in range(2):
            operator, reports = _modal_operator()
            assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
            MatchColorReference.modal(operator, context, _event("ESC"))
            assert not reports
        assert read_reference.call_count == 1
    bpy.context.scene.anyimage_settings.color_reference = None


def test_reference_cache_refreshes_consecutive_pixel_edits(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rgba = np.full((4, 4, 4), (0.7, 0.2, 0.1, 1.0), dtype=np.float32)
    reference = _image("Reference", rgba)
    bpy.context.scene.anyimage_settings.color_reference = reference
    first = reference_cache.get_color_reference(reference)
    for color in [(0.1, 0.7, 0.2), (0.2, 0.1, 0.7)]:
        rgba[..., :3] = color
        reference.pixels.foreach_set(np.flipud(rgba).ravel())
        reference.update()
        reference_cache.refresh_color_references()
        second = reference_cache.get_color_reference(reference)
        assert second is not first
        np.testing.assert_allclose(second.rgba, rgba, atol=1/255)
        first = second


def test_shared_reference_refreshes_scenes_only_after_pixel_changes(
    registered_color_reference,
):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rgba = np.full((4, 4, 4), (0.7, 0.2, 0.1, 1.0), dtype=np.float32)
    reference = _image("Reference", rgba)
    bpy.context.scene.anyimage_settings.color_reference = reference
    other = bpy.data.scenes.new("Other scene")
    other.anyimage_settings.color_reference = reference

    with patch("anyimage.properties.update_color_reference_palette") as update:
        reference_cache.refresh_color_references()
        update.assert_not_called()
        rgba[..., :3] = (0.1, 0.7, 0.2)
        reference.pixels.foreach_set(np.flipud(rgba).ravel())
        reference.update()
        reference_cache.refresh_color_references()
        assert update.call_count == 2
        assert {call.args[0].id_data.name for call in update.call_args_list} == {
            bpy.context.scene.name,
            other.name,
        }



def test_color_reference_gallery_selects_only_candidates(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    _image("Reference_depth.exr", np.full((2, 2, 4), (0.6, 0.2, 0.1, 1.0)))
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
    reference = _image("Persistent reference", np.full((2, 2, 4), (0.4, 0.3, 0.2, 1.0)))
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
    bpy.context.scene.anyimage_settings.color_reference = reference
    first = reference_cache.get_color_reference(reference)
    Image.new("RGB", (4, 4), "blue").save(path)
    reference.reload()
    reference_cache.refresh_color_references()
    second = reference_cache.get_color_reference(reference)
    assert second is not first
    assert second.rgba[0, 0, 2] > .9
    reference_cache.register()
    try:
        for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.undo_post, bpy.app.handlers.redo_post):
            assert reference_cache.clear_color_references in handlers
            reference_cache.clear_color_references(None)
            current = reference_cache.get_color_reference(reference)
            assert current is not second
            second = current
    finally:
        reference_cache.unregister()
    assert not bpy.app.timers.is_registered(reference_cache.refresh_color_references)


def test_failed_reference_preparation_does_not_keep_old_pixels(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    settings = bpy.context.scene.anyimage_settings
    settings.color_reference = reference
    reference.pixels.foreach_set(np.zeros(64, dtype=np.float32))
    reference.update()
    reference_cache.refresh_color_references()
    assert settings.color_reference_palette_count == 0
    with pytest.raises(ValueError, match="no visible"):
        reference_cache.get_color_reference(reference)
    with patch("anyimage.properties.update_color_reference_palette") as update:
        reference_cache.refresh_color_references()
        update.assert_not_called()


def test_byte_reference_is_encoded_once_and_palette_is_linear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (.5, .2, .1, 1)))
    prepared = reference_cache.get_color_reference(reference)
    pixels = image_rgba(reference)[0, 0, :3]
    np.testing.assert_allclose(prepared.transfer.mean, pixels, atol=1e-6)
    np.testing.assert_allclose(prepared.colors[0], srgb_to_linear_rgb(pixels), atol=.005)


def test_match_rejects_missing_same_or_animated_images():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = _image("Static", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    context = _context(_empty("Owner", image))

    assert not MatchColorReference.poll(context)
    context.scene.anyimage_settings.color_reference = image
    assert not MatchColorReference.poll(context)
    image.source = "SEQUENCE"
    assert current_color_reference(context) is None


@pytest.mark.parametrize("target_name", ["Target.png", "Target_color.png.001"])
def test_match_transforms_all_rgb_and_preserves_target_alpha(target_name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference_rgba = np.full((8, 8, 4), (0.65, 0.25, 0.08, 1.0), dtype=np.float32)
    reference_rgba[0, 0] = (0.0, 0.0, 1.0, 0.0)
    target_rgba = np.full((8, 8, 4), (0.06, 0.16, 0.5, 1.0), dtype=np.float32)
    target_rgba[0, 0, 3] = 0.0
    target_rgba[0, 1, 3] = 0.5
    reference = _image("Reference.png", reference_rgba)
    target = _image(target_name, target_rgba)
    target.colorspace_settings.name = "Non-Color"
    owner = _empty("Target owner", target)
    context = _context(owner, reference)

    assert MatchColorReference.poll(context)
    assert _execute(MatchColorReference, context) == {"FINISHED"}
    result = image_rgba(owner.data)

    np.testing.assert_allclose(result[..., 3], target_rgba[..., 3], atol=1 / 255)
    assert not np.allclose(result[0, 0, :3], target_rgba[0, 0, :3], atol=1 / 255)
    assert owner.data.name == target_name
    assert owner.data.colorspace_settings.name == "Non-Color"


def test_match_isolates_an_image_shared_with_another_empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (0.7, 0.3, 0.1, 1.0)))
    source = _image("Shared.png", np.full((4, 4, 4), (0.1, 0.2, 0.6, 1.0)))
    first = _empty("First", source)
    second = _empty("Second", source)
    before = image_rgba(source).copy()

    assert _execute(MatchColorReference, _context(first, reference)) == {"FINISHED"}

    assert first.data != source
    assert second.data == source
    np.testing.assert_array_equal(image_rgba(second.data), before)
    assert not np.allclose(image_rgba(first.data)[..., :3], before[..., :3], atol=1 / 255)


def test_repeated_match_uses_current_pixels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    warm = _image("Warm", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    green = _image("Green", np.full((8, 8, 4), (0.15, 0.65, 0.2, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    assert _execute(MatchColorReference, _context(owner, warm)) == {"FINISHED"}
    first_result = image_rgba(owner.data).copy()
    assert owner.data == source

    assert _execute(MatchColorReference, _context(owner, green)) == {"FINISHED"}
    assert owner.data == source
    expected = linear_rgba_to_image(source, apply_color_match(
        build_color_match(
            prepare_color_reference(image_rgba_to_linear(green, image_rgba(green))),
            image_rgba_to_linear(source, first_result),
        ), mix=0.5,
    ))
    np.testing.assert_allclose(image_rgba(owner.data), expected, atol=1 / 255)


def test_repeated_match_keeps_one_isolated_working_image():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first_reference = _image("First reference", np.full((4, 4, 4), (0.7, 0.3, 0.1, 1.0)))
    second_reference = _image("Second reference", np.full((4, 4, 4), (0.2, 0.65, 0.15, 1.0)))
    source = _image("Shared", np.full((4, 4, 4), (0.1, 0.2, 0.6, 1.0)))
    first = _empty("First", source)
    second = _empty("Second", source)

    assert _execute(MatchColorReference, _context(first, first_reference)) == {"FINISHED"}
    working = first.data
    assert working != source and second.data == source

    assert _execute(MatchColorReference, _context(first, second_reference)) == {"FINISHED"}
    assert first.data == working
    assert second.data == source


def test_match_rejects_a_target_changed_during_processing():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (0.7, 0.3, 0.1, 1.0)))
    source = _image("Source", np.full((4, 4, 4), (0.1, 0.2, 0.6, 1.0)))
    replacement = _image("Replacement", np.full((4, 4, 4), (0.2, 0.2, 0.2, 1.0)))
    owner = _empty("Owner", source)
    context = _context(owner, reference)
    reports = []

    def change_target(_reference, target, **_options):
        owner.data = replacement
        return build_color_match(_reference, target, **_options)

    with patch.object(color_reference, "build_color_match", side_effect=change_target):
        result = MatchColorReference.execute(
            SimpleNamespace(report=lambda level, message: reports.append((level, message))),
            context,
        )

    assert result == {"CANCELLED"}
    assert owner.data == replacement
    assert any("no longer available" in message for _level, message in reports)


@pytest.mark.parametrize("cancel_event", ["RIGHTMOUSE", "ESC"])
def test_modal_match_updates_controls_and_cancels_cleanly(cancel_event):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()

    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    preview_name = operator._preview_image.name
    assert owner.data == source
    assert operator._mix == pytest.approx(0.5)
    operator._last_preview_time = 0.0
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=200, y=140, value="NOTHING"),
    ) == {"RUNNING_MODAL"}
    assert operator._mix == pytest.approx(0.75)
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=300, y=140, value="NOTHING", shift=True),
    ) == {"RUNNING_MODAL"}
    assert operator._mix == pytest.approx(0.8)
    assert context.area.tag_redraw.called

    assert MatchColorReference.modal(operator, context, _event(cancel_event)) == {"CANCELLED"}
    assert owner.data == source
    assert bpy.data.images.get(preview_name) is None
    assert not reports


def test_modal_match_throttles_preview_updates():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, _reports = _modal_operator()
    MatchColorReference.invoke(operator, context, _event("LEFTMOUSE"))
    with (
        patch.object(
            color_reference.time,
            "perf_counter",
            return_value=operator._last_preview_time,
        ),
        patch.object(color_reference, "update_color_preview_image") as update,
    ):
        MatchColorReference.modal(
            operator,
            context,
            _event("MOUSEMOVE", x=120, y=120, value="NOTHING"),
        )

    update.assert_not_called()
    operator._last_preview_time = 0
    with (
        patch.object(color_reference, "build_color_match") as build,
        patch.object(color_reference, "update_color_preview_image") as update,
    ):
        MatchColorReference.modal(operator, context, _event("TIMER", value="NOTHING"))
        update.assert_called_once()
        build.assert_not_called()
    with patch.object(color_reference, "update_color_preview_image") as update:
        MatchColorReference.modal(operator, context, _event("MOUSEMOVE", x=120, y=200))
        update.assert_not_called()
    MatchColorReference.modal(operator, context, _event("ESC"))
    context.window_manager.event_timer_remove.assert_called_once()


@pytest.mark.parametrize("changed", ["reference", "target", "binding"])
def test_modal_rejects_external_changes_and_releases_snapshots(changed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    target = _image("Target", np.full((4, 4, 4), (.1, .2, .6, 1)))
    owner = _empty("Owner", target)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    preview_name = operator._preview_image.name
    if changed == "binding":
        owner.data = reference
    else:
        image = reference if changed == "reference" else target
        image.pixels.foreach_set(np.tile(np.asarray((.4, .5, .1, 1), dtype=np.float32), 16))
        image.update()
    before = image_rgba(owner.data)
    assert MatchColorReference.modal(operator, context, _event("RET")) == {"CANCELLED"}
    np.testing.assert_array_equal(image_rgba(owner.data), before)
    assert bpy.data.images.get(preview_name) is None
    assert operator._reference is None and operator._target_rgba is None
    assert reports


def test_zero_mix_confirmation_preserves_image_identity_and_pixels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    target = _image("Target", np.full((4, 4, 4), (.1, .2, .6, 1)))
    owner = _empty("Owner", target)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    before = image_rgba(target)
    MatchColorReference.invoke(operator, context, _event("LEFTMOUSE"))
    operator._mix = 0
    with patch.object(color_reference, "build_color_match") as build:
        assert MatchColorReference.modal(operator, context, _event("RET")) == {"FINISHED"}
        build.assert_not_called()
    assert owner.data == target
    np.testing.assert_array_equal(image_rgba(target), before)
    assert not reports


@pytest.mark.parametrize("confirm_event", ["LEFTMOUSE", "RET"])
def test_modal_match_confirms_one_full_resolution_result(confirm_event):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    before = image_rgba(source).copy()

    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    preview_name = operator._preview_image.name
    assert owner.data == source
    operator._mix = 0.25

    assert MatchColorReference.modal(operator, context, _event(confirm_event)) == {"FINISHED"}
    assert tuple(owner.data.size) == (8, 8)
    assert not np.allclose(image_rgba(owner.data)[..., :3], before[..., :3], atol=1 / 255)
    assert bpy.data.images.get(preview_name) is None
    assert not reports


def test_match_undo_redo_restores_pixels_and_keeps_reference(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Undo reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Undo target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Undo owner", source)
    bpy.context.view_layer.objects.active = owner
    owner.select_set(True)
    bpy.context.scene.anyimage_settings.color_reference = reference
    before = image_rgba(source).copy()
    bpy.context.preferences.edit.use_global_undo = True

    bpy.ops.ed.undo_push(message="Before color match")
    assert bpy.ops.anyimage.match_color_reference("EXEC_DEFAULT", True) == {"FINISHED"}
    after = image_rgba(owner.data).copy()
    assert not np.allclose(after[..., :3], before[..., :3], atol=1 / 255)

    assert bpy.ops.ed.undo() == {"FINISHED"}
    owner = bpy.data.objects["Undo owner"]
    np.testing.assert_allclose(image_rgba(owner.data), before, atol=1 / 255)
    assert bpy.context.scene.anyimage_settings.color_reference.name == "Undo reference"

    assert bpy.ops.ed.redo() == {"FINISHED"}
    owner = bpy.data.objects["Undo owner"]
    np.testing.assert_allclose(image_rgba(owner.data), after, atol=1 / 255)
