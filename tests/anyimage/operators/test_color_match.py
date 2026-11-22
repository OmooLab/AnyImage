from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import bpy
import numpy as np
import pytest

from tests.support.color_reference import create_clipboard_image, create_image_empty, registered_color_reference, isolate_reference_cache
from anyimage.common import color_reference as reference_cache
from anyimage.common.color_match import build_color_mapping, build_color_match, apply_color_match
from anyimage.common.color_space import image_rgba_to_linear, linear_rgba_to_image
from anyimage.common.image import image_rgba
from anyimage.operators import color_match
from anyimage.operators.color_match import (
    MatchColorReference,
    current_color_reference,
)


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
        "_update_preview",
        "_restore_preview",
        "_confirm_preview",
        "_add_preview_handler",
        "_tag_redraw",
        "_finish",
    ):
        setattr(operator, name, MethodType(getattr(MatchColorReference, name), operator))
    return operator, reports


def _modal_context(owner, reference):
    context = _context(owner, reference)
    context.area = SimpleNamespace(tag_redraw=Mock())
    context.workspace = Mock()
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


def test_match_rejects_missing_same_or_animated_images():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = create_clipboard_image("Static", np.full((2, 2, 4), (0.2, 0.3, 0.4, 1.0)))
    context = _context(create_image_empty("Owner", image))

    assert not MatchColorReference.poll(context)
    context.scene.anyimage_settings.color_reference = image
    assert not MatchColorReference.poll(context)
    image.source = "SEQUENCE"
    assert current_color_reference(context) is None


def test_match_transforms_all_rgb_and_preserves_target_alpha():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference_rgba = np.full((8, 8, 4), (0.65, 0.25, 0.08, 1.0), dtype=np.float32)
    reference_rgba[0, 0] = (0.0, 0.0, 1.0, 0.0)
    target_rgba = np.full((8, 8, 4), (0.06, 0.16, 0.5, 1.0), dtype=np.float32)
    target_rgba[0, 0, 3] = 0.0
    target_rgba[0, 1, 3] = 0.5
    reference = create_clipboard_image("Reference.png", reference_rgba)
    target = create_clipboard_image("Target_color.png.001", target_rgba)
    target.colorspace_settings.name = "Non-Color"
    owner = create_image_empty("Target owner", target)
    context = _context(owner, reference)

    assert MatchColorReference.poll(context)
    assert _execute(MatchColorReference, context) == {"FINISHED"}
    result = image_rgba(owner.data)

    np.testing.assert_allclose(result[..., 3], target_rgba[..., 3], atol=1 / 255)
    assert not np.allclose(result[0, 0, :3], target_rgba[0, 0, :3], atol=1 / 255)
    assert owner.data.name == "Target_color.png.001"
    assert owner.data.colorspace_settings.name == "Non-Color"


@pytest.mark.parametrize("space", ["sRGB", "AgX Base sRGB", "Non-Color"])
def test_match_preview_and_full_size_result_preserve_color_settings(space):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference_rgba = np.full((4, 4, 4), (.7, .3, .1, 1))
    reference_rgba[:, ::2] = (.1, .8, .1, 1)
    reference = create_clipboard_image("Reference", reference_rgba)
    stripes = np.full((8, 1023, 4), (.1, .2, .6, .5))
    stripes[:, ::2] = (.7, .1, .2, .5)
    source = create_clipboard_image("Target_color", stripes)
    source.colorspace_settings.name = space
    source.alpha_mode = "CHANNEL_PACKED"
    reference.colorspace_settings.name = space
    before = image_rgba(source)
    direct = create_image_empty("Direct", source)
    owner = create_image_empty("Owner", source)
    assert _execute(MatchColorReference, _context(direct, reference)) == {"FINISHED"}
    expected = image_rgba(direct.data)
    assert not np.array_equal(expected, before)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    preview = image_rgba(owner.data)
    assert preview.shape[1] < before.shape[1]
    np.testing.assert_allclose(preview[0, 0], expected[0, 0], atol=1 / 255)
    assert (source.colorspace_settings.name, source.alpha_mode) == (space, "CHANNEL_PACKED")
    np.testing.assert_array_equal(image_rgba(source), before)
    assert MatchColorReference.modal(operator, context, _event("RET")) == {"FINISHED"}
    assert (owner.data.colorspace_settings.name, owner.data.alpha_mode) == (space, "CHANNEL_PACKED")
    np.testing.assert_array_equal(image_rgba(owner.data), expected)
    assert not reports


def test_match_isolates_an_image_shared_with_another_empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (0.7, 0.3, 0.1, 1.0)))
    source = create_clipboard_image("Shared.png", np.full((4, 4, 4), (0.1, 0.2, 0.6, 1.0)))
    first = create_image_empty("First", source)
    second = create_image_empty("Second", source)
    before = image_rgba(source).copy()

    assert _execute(MatchColorReference, _context(first, reference)) == {"FINISHED"}

    assert first.data != source
    assert second.data == source
    np.testing.assert_array_equal(image_rgba(second.data), before)
    assert not np.allclose(image_rgba(first.data)[..., :3], before[..., :3], atol=1 / 255)


def test_repeated_match_uses_current_pixels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    warm = create_clipboard_image("Warm", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    green = create_clipboard_image("Green", np.full((8, 8, 4), (0.15, 0.65, 0.2, 1.0)))
    source = create_clipboard_image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = create_image_empty("Owner", source)
    assert _execute(MatchColorReference, _context(owner, warm)) == {"FINISHED"}
    first_result = image_rgba(owner.data).copy()
    assert owner.data == source

    assert _execute(MatchColorReference, _context(owner, green)) == {"FINISHED"}
    assert owner.data == source
    linear = image_rgba_to_linear(source, first_result)
    mapping = build_color_mapping(reference_cache.get_color_reference(green).transfer, linear)
    expected = linear_rgba_to_image(source, apply_color_match(build_color_match(mapping, linear)))
    np.testing.assert_allclose(image_rgba(owner.data), expected, atol=1 / 255)


def test_repeated_match_keeps_one_isolated_working_image():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    first_reference = create_clipboard_image("First reference", np.full((4, 4, 4), (0.7, 0.3, 0.1, 1.0)))
    second_reference = create_clipboard_image("Second reference", np.full((4, 4, 4), (0.2, 0.65, 0.15, 1.0)))
    source = create_clipboard_image("Shared", np.full((4, 4, 4), (0.1, 0.2, 0.6, 1.0)))
    first = create_image_empty("First", source)
    second = create_image_empty("Second", source)

    assert _execute(MatchColorReference, _context(first, first_reference)) == {"FINISHED"}
    working = first.data
    assert working != source and second.data == source

    assert _execute(MatchColorReference, _context(first, second_reference)) == {"FINISHED"}
    assert first.data == working
    assert second.data == source


def test_modal_match_updates_controls_and_cancels_cleanly():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = create_clipboard_image("Target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = create_image_empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()

    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    images_before = tuple(image for image in bpy.data.images if image != owner.data)
    context.workspace.status_text_set.assert_called_once_with(color_match.draw_match_status)
    assert owner.data == operator._preview_image
    assert not MatchColorReference.poll(context)
    assert operator._color == pytest.approx(0.5)
    assert operator._lightness == pytest.approx(0.0)
    operator._last_preview_time = 0.0
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=200, y=140, value="NOTHING"),
    ) == {"RUNNING_MODAL"}
    assert operator._color == pytest.approx(0.75)
    assert operator._lightness == pytest.approx(0.1)
    assert MatchColorReference.modal(
        operator,
        context,
        _event("MOUSEMOVE", x=300, y=140, value="NOTHING", shift=True),
    ) == {"RUNNING_MODAL"}
    assert operator._color == pytest.approx(0.8)
    assert context.area.tag_redraw.called

    assert MatchColorReference.modal(operator, context, _event("ESC")) == {"CANCELLED"}
    assert owner.data == source
    assert operator._preview_image is None
    context.workspace.status_text_set.assert_called_with(None)
    assert tuple(bpy.data.images) == images_before
    assert not reports


@pytest.mark.parametrize("changed", ["reference", "target", "binding", "color_space", "alpha_mode"])
def test_modal_rejects_external_changes_and_releases_snapshots(changed):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    target = create_clipboard_image("Target", np.full((4, 4, 4), (.1, .2, .6, 1)))
    owner = create_image_empty("Owner", target)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    images_before = tuple(image for image in bpy.data.images if image != operator._preview_image)
    if changed == "color_space":
        target.colorspace_settings.name = "Non-Color"
    elif changed == "alpha_mode":
        target.alpha_mode = "CHANNEL_PACKED"
    elif changed == "binding":
        owner.data = reference
    else:
        image = reference if changed == "reference" else target
        image.pixels.foreach_set(np.tile(np.asarray((.4, .5, .1, 1), dtype=np.float32), 16))
        image.update()
    before = image_rgba(reference if changed == "binding" else target)
    assert MatchColorReference.modal(operator, context, _event("RET")) == {"CANCELLED"}
    np.testing.assert_array_equal(image_rgba(owner.data), before)
    assert operator._preview_image is None
    context.workspace.status_text_set.assert_called_with(None)
    assert tuple(bpy.data.images) == images_before
    assert reports


def test_zero_controls_confirmation_preserves_image_identity_and_pixels():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.7, .3, .1, 1)))
    target = create_clipboard_image("Target", np.full((4, 4, 4), (.1, .2, .6, 1)))
    owner = create_image_empty("Owner", target)
    context = _modal_context(owner, reference)
    operator, reports = _modal_operator()
    before = image_rgba(target)
    MatchColorReference.invoke(operator, context, _event("LEFTMOUSE"))
    operator._color = 0
    operator._lightness = 0
    assert MatchColorReference.modal(operator, context, _event("RET")) == {"FINISHED"}
    assert owner.data == target
    np.testing.assert_array_equal(image_rgba(target), before)
    assert not reports


def test_match_undo_redo_restores_pixels_and_keeps_reference(registered_color_reference):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Undo reference", np.full((8, 8, 4), (0.7, 0.25, 0.08, 1.0)))
    source = create_clipboard_image("Undo target", np.full((8, 8, 4), (0.08, 0.2, 0.55, 1.0)))
    owner = create_image_empty("Undo owner", source)
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


def test_cancel_after_preview_image_is_removed():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.7, .2, .1, 1)))
    source = create_clipboard_image("Source", np.full((4, 4, 4), (.1, .2, .7, 1)))
    owner = create_image_empty("Owner", source)
    context = _modal_context(owner, reference)
    operator, _ = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    bpy.data.images.remove(owner.data)

    assert MatchColorReference.modal(operator, context, _event("ESC")) == {"CANCELLED"}
    assert owner.data == source
    context.window_manager.event_timer_remove.assert_called_once()


def test_deleted_reference_cancels_and_releases_interaction_resources():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.7, .2, .1, 1)))
    target = create_clipboard_image("Target", np.full((4, 4, 4), (.1, .2, .7, 1)))
    context = _modal_context(create_image_empty("Owner", target), reference)
    operator, reports = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    bpy.data.images.remove(reference)
    assert MatchColorReference.modal(operator, context, _event("RET")) == {"CANCELLED"}
    assert operator._timer is None and operator._preview_image is None
    assert context.object.data == target
    assert reports


@pytest.mark.parametrize("node_type", ["ShaderNodeTexEnvironment", "ShaderNodeTexImage"])
def test_world_preview_updates_before_confirmation(node_type):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    reference = create_clipboard_image("Reference", np.full((4, 4, 4), (.8, .1, .1, 1)))
    source = create_clipboard_image("Source", np.full((4, 4, 4), (.1, .2, .7, 1)))
    world = bpy.data.worlds.new("Preview World")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    node = tree.nodes.new(node_type)
    node.image = source
    tree.nodes.active = node
    tree.links.new(node.outputs["Color"], tree.nodes["Background"].inputs["Color"])
    context = _modal_context(None, reference)
    context.space_data = SimpleNamespace(type="NODE_EDITOR", tree_type="ShaderNodeTree",
                                         shader_type="WORLD", id=world, edit_tree=tree)
    viewport = SimpleNamespace(type="VIEW_3D", tag_redraw=Mock())
    context.window_manager.windows = [SimpleNamespace(screen=SimpleNamespace(areas=[viewport]))]
    operator, reports = _modal_operator()
    assert MatchColorReference.invoke(operator, context, _event("LEFTMOUSE")) == {"RUNNING_MODAL"}
    before = image_rgba(node.image).copy()
    operator._last_preview_time = 0
    viewport.tag_redraw.reset_mock()
    assert MatchColorReference.modal(operator, context, _event("MOUSEMOVE", x=275)) == {"RUNNING_MODAL"}
    bpy.context.view_layer.update()
    evaluated = world.evaluated_get(bpy.context.evaluated_depsgraph_get())
    assert not np.allclose(image_rgba(evaluated.node_tree.nodes[node.name].image), before)
    viewport.tag_redraw.assert_called_once()
    assert MatchColorReference.modal(operator, context, _event("ESC")) == {"CANCELLED"}
    assert node.image == source
    assert not reports
