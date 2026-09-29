from types import MethodType, SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest

from anyimage import properties
from anyimage.common import material as material_data
from anyimage.common.color_match import match_color_reference
from anyimage.common.image import image_rgba
from anyimage.common.image_target import ImageEditTarget, object_color_texture
from anyimage.operators import color_reference
from anyimage.operators.color_reference import (
    ColorMatchPreview,
    MatchColorReference,
    SetColorReference,
    create_color_preview_image,
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
    for name in ("_preview_pixels", "_commit", "_update_header", "_restore_preview"):
        setattr(operator, name, MethodType(getattr(MatchColorReference, name), operator))
    return operator, reports


def _modal_context(owner, reference):
    context = _context(owner, reference)
    context.area = SimpleNamespace(header_text_set=Mock())
    context.window_manager = SimpleNamespace(modal_handler_add=Mock())
    return context


def _event(event_type, *, x=100, y=100, value="PRESS", shift=False):
    return SimpleNamespace(
        type=event_type,
        value=value,
        mouse_x=x,
        mouse_y=y,
        shift=shift,
    )


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
    for operator in (SetColorReference, MatchColorReference):
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


def test_set_reference_replaces_scene_reference_without_editing_pixels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first = _image("First", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    second = _image("Second", np.full((2, 2, 4), (0.6, 0.2, 0.1, 1.0)))
    context = _context(_empty("First owner", first))
    before = image_rgba(first).copy()

    assert SetColorReference.poll(context)
    assert _execute(SetColorReference, context) == {"FINISHED"}
    assert current_color_reference(context) == first
    np.testing.assert_array_equal(image_rgba(first), before)

    context.object = _empty("Second owner", second)
    assert _execute(SetColorReference, context) == {"FINISHED"}
    assert current_color_reference(context) == second

    context.scene.anyimage_settings.color_reference = None
    assert current_color_reference(context) is None


def test_set_reference_uses_the_current_pixels_of_a_matched_image():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    warm = _image("Warm", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target.png", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    assert _execute(MatchColorReference, _context(owner, warm)) == {"FINISHED"}
    matched = image_rgba(owner.data).copy()
    context = _context(owner)

    assert SetColorReference.poll(context)
    assert _execute(SetColorReference, context) == {"FINISHED"}
    assert current_color_reference(context) == owner.data
    np.testing.assert_array_equal(image_rgba(current_color_reference(context)), matched)


def test_scene_reference_survives_save_and_reopen(tmp_path, registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Persistent reference", np.full((2, 2, 4), (0.4, 0.3, 0.2, 1.0)))
    reference.use_fake_user = True
    bpy.context.scene.anyimage_settings.color_reference = reference
    path = tmp_path / "color-reference.blend"

    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.wm.open_mainfile(filepath=str(path))

    assert bpy.context.scene.anyimage_settings.color_reference == bpy.data.images["Persistent reference"]


def test_reference_and_match_reject_missing_same_or_animated_images():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = _image("Static", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    context = _context(_empty("Owner", image))

    assert not MatchColorReference.poll(context)
    context.scene.anyimage_settings.color_reference = image
    assert not MatchColorReference.poll(context)
    image.source = "SEQUENCE"
    assert not SetColorReference.poll(context)
    assert current_color_reference(context) is None


def test_match_transforms_all_rgb_and_preserves_target_alpha():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference_rgba = np.full((8, 8, 4), (0.65, 0.25, 0.08, 1.0), dtype=np.float32)
    reference_rgba[0, 0] = (0.0, 0.0, 1.0, 0.0)
    target_rgba = np.full((8, 8, 4), (0.06, 0.16, 0.5, 1.0), dtype=np.float32)
    target_rgba[0, 0, 3] = 0.0
    target_rgba[0, 1, 3] = 0.5
    reference = _image("Reference.png", reference_rgba)
    target = _image("Target.png", target_rgba)
    target.colorspace_settings.name = "Non-Color"
    owner = _empty("Target owner", target)
    context = _context(owner, reference)

    assert MatchColorReference.poll(context)
    assert _execute(MatchColorReference, context) == {"FINISHED"}
    result = image_rgba(owner.data)

    np.testing.assert_allclose(result[..., 3], target_rgba[..., 3], atol=1 / 255)
    assert not np.allclose(result[0, 0, :3], target_rgba[0, 0, :3], atol=1 / 255)
    assert owner.data.name == "Target.png"
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
    expected = match_color_reference(image_rgba(green), first_result)
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
        return target.copy()

    with patch.object(color_reference, "match_color_reference", side_effect=change_target):
        result = MatchColorReference.execute(
            SimpleNamespace(report=lambda level, message: reports.append((level, message))),
            context,
        )

    assert result == {"CANCELLED"}
    assert owner.data == replacement
    assert any("no longer available" in message for _level, message in reports)


def test_preview_binding_restores_an_empty_without_changing_shared_image():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = _image("Source", np.full((4, 6, 4), (0.1, 0.2, 0.6, 1.0)))
    first = _empty("First", source)
    second = _empty("Second", source)
    target = ImageEditTarget.capture(_context(first))
    preview_image = create_color_preview_image(source, image_rgba(source)[::2, ::2])
    preview_name = preview_image.name

    preview = ColorMatchPreview.bind(target, preview_image)

    assert first.data == preview_image
    assert second.data == source
    assert preview.restore()
    assert first.data == source
    assert second.data == source
    assert bpy.data.images.get(preview_name) is None
    target.validate()


def test_preview_binding_isolates_and_removes_a_shared_material():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = _image("Source", np.full((4, 6, 4), (0.1, 0.2, 0.6, 1.0)))
    first, material = _image_object("First", source)
    second_mesh = bpy.data.meshes.new("Second")
    second_mesh.materials.append(material)
    second = bpy.data.objects.new("Second", second_mesh)
    second["o_image_object"] = True
    bpy.context.scene.collection.objects.link(second)
    target = ImageEditTarget.capture(_context(first))
    preview_image = create_color_preview_image(source, image_rgba(source)[::2, ::2])

    preview = ColorMatchPreview.bind(target, preview_image)
    copied_material = first.active_material
    copied_material_name = copied_material.name

    assert copied_material != material
    assert second.active_material == material
    assert object_color_texture(first).image == preview_image
    assert preview.restore()
    assert first.active_material == material
    assert second.active_material == material
    assert bpy.data.materials.get(copied_material_name) is None
    target.validate()


def test_preview_binding_restores_a_direct_texture_node():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = _image("Source", np.full((4, 6, 4), (0.1, 0.2, 0.6, 1.0)))
    owner, material = _image_object("Owner", source)
    target = ImageEditTarget.capture(_context(owner))
    pixels = image_rgba(source)[::2, ::2]
    preview_image = create_color_preview_image(source, pixels)
    preview = ColorMatchPreview.bind(target, preview_image)

    changed = pixels.copy()
    changed[..., 0] = 0.8
    preview.update(changed)

    assert owner.active_material == material
    assert object_color_texture(owner).image == preview_image
    np.testing.assert_allclose(image_rgba(preview_image), changed, atol=1 / 255)
    assert preview.restore()
    assert object_color_texture(owner).image == source
    target.validate()


def test_preview_restore_does_not_overwrite_an_external_target_change():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source = _image("Source", np.full((4, 6, 4), (0.1, 0.2, 0.6, 1.0)))
    replacement = _image("Replacement", np.full((4, 6, 4), (0.2, 0.2, 0.2, 1.0)))
    owner = _empty("Owner", source)
    target = ImageEditTarget.capture(_context(owner))
    preview_image = create_color_preview_image(source, image_rgba(source)[::2, ::2])
    preview_name = preview_image.name
    preview = ColorMatchPreview.bind(target, preview_image)

    owner.data = replacement

    assert not preview.restore()
    assert owner.data == replacement
    assert bpy.data.images.get(preview_name) is None


@pytest.mark.parametrize("cancel_event", ["RIGHTMOUSE", "ESC"])
def test_modal_match_updates_controls_and_cancels_cleanly(cancel_event):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()

    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    preview_name = owner.data.name
    operator._last_preview_time = 0.0
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=200, y=140, value="NOTHING"),
    ) == {"RUNNING_MODAL"}
    assert operator._match == pytest.approx(1.25)
    assert operator._contrast == pytest.approx(0.1)
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=300, y=140, value="NOTHING", shift=True),
    ) == {"RUNNING_MODAL"}
    assert operator._match == pytest.approx(1.3)
    assert context.area.header_text_set.call_args.args[0].startswith("Match 130%")

    assert MatchColorReference.modal(operator, context, _event(cancel_event)) == {"CANCELLED"}
    assert owner.data == source
    assert bpy.data.images.get(preview_name) is None
    assert context.area.header_text_set.call_args.args == (None,)
    assert not reports


def test_modal_match_throttles_preview_updates():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = _image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = _image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = _empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, _reports = _modal_operator()
    MatchColorReference.invoke(operator, context, _event("LEFTMOUSE"))
    operator._preview.update = Mock()

    with patch.object(color_reference.time, "perf_counter", return_value=operator._last_preview_time):
        MatchColorReference.modal(
            operator,
            context,
            _event("MOUSEMOVE", x=120, y=120, value="NOTHING"),
        )

    operator._preview.update.assert_not_called()
    MatchColorReference.modal(operator, context, _event("ESC"))


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
    preview_name = owner.data.name
    operator._contrast = 0.25

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
