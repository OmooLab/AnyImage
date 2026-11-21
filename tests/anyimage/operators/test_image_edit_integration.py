from types import SimpleNamespace
from unittest.mock import Mock
import bpy
import numpy as np
import pytest
from mathutils import Matrix


from anyimage.common import image as image_data
from anyimage.common import image_gesture
from anyimage.common.selection import SelectionMask
from anyimage.common.color_space import srgb_to_linear_rgb, linear_rgb_to_srgb
from anyimage.operators import mask_tool as edit_mask
from anyimage.operators.frame_tool import operators as edit_frame


@pytest.mark.parametrize("change", ["rename", "delete", "deselect", "add"])
def test_frame_drag_requires_the_same_selected_sources(monkeypatch, change):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Frame", width=2, height=2)

    def image_empty(name):
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "IMAGE"
        obj.data = image
        bpy.context.collection.objects.link(obj)
        return obj

    active, original = image_empty("Active"), image_empty("Other")
    context = SimpleNamespace(
        active_object=active, selected_objects=(active, original),
        area=Mock(), region=Mock(), workspace=SimpleNamespace(status_text_set=Mock()),
        window_manager=Mock(),
    )
    operator = SimpleNamespace(_draw_overlay=Mock(), _finish=Mock(), report=Mock())
    monkeypatch.setattr(bpy.types.SpaceView3D, "draw_handler_add", Mock())
    composite = Mock()
    monkeypatch.setattr(edit_frame, "apply_frame", composite)
    press = SimpleNamespace(mouse_region_x=0, mouse_region_y=0)
    assert edit_frame.FrameImages.invoke(operator, context, press) == {"RUNNING_MODAL"}
    if change == "delete":
        bpy.data.objects.remove(original, do_unlink=True)
        context.selected_objects = (active, image_empty("Other"))
    elif change == "rename":
        original.name = "Renamed"
        image_empty("Other")
    elif change == "deselect":
        context.selected_objects = (active,)
    else:
        context.selected_objects += (image_empty("New"),)
    release = SimpleNamespace(type="LEFTMOUSE", value="RELEASE", mouse_region_x=10, mouse_region_y=10)
    result = edit_frame.FrameImages.modal(operator, context, release)
    if change != "rename":
        assert result == {"CANCELLED"}
        composite.assert_not_called()
    else:
        assert result == {"FINISHED"}
        assert composite.call_args.args[1] == (original, active)


def apply_frame(monkeypatch, objects, frame, size):
    """Use the actual color and image transaction with deterministic viewport geometry."""
    context = SimpleNamespace(
        active_object=objects[-1],
        region=SimpleNamespace(width=size[0], height=size[1]),
        region_data=SimpleNamespace(
            perspective_matrix=Matrix.Identity(4), view_matrix=Matrix.Identity(4),
            is_perspective=False,
        ),
    )
    monkeypatch.setattr(edit_frame, "configured_max_frame_resolution", lambda _: max(size))
    monkeypatch.setattr(edit_frame, "frame_output_size", lambda *_: size)
    monkeypatch.setattr(edit_frame, "frame_result_transform", lambda *_: (Matrix.Identity(4), 2.0))
    return edit_frame.apply_frame(context, objects, frame).data


def test_image_edit_result_uses_complete_shared_source_name():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Poster.png", width=2, height=2, alpha=True)
    source = bpy.data.objects.new("Poster", None)
    source.empty_display_type = "IMAGE"
    source.data = source_image
    shared = bpy.data.objects.new("Poster Shared", None)
    shared.empty_display_type = "IMAGE"
    shared.data = source_image
    bpy.context.collection.objects.link(source)
    bpy.context.collection.objects.link(shared)

    result_image = image_data.create_image_edit_result(
        source_image,
        np.zeros(4 * 4 * 4, dtype=np.float32),
        (4, 4),
    )
    result_image = image_data.replace_empty_image(source, result_image)

    assert shared.data == source_image
    assert source_image.alpha_mode == "STRAIGHT"
    assert result_image.alpha_mode == "STRAIGHT"
    assert source.use_empty_image_alpha
    assert source.data == result_image
    assert result_image.name == "Poster.png.001"
    assert "_color" not in result_image.name


def test_image_edit_result_recovers_unshared_source_name():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Poster.png", width=2, height=2, alpha=True)
    source = bpy.data.objects.new("Poster", None)
    source.empty_display_type = "IMAGE"
    source.data = source_image
    bpy.context.collection.objects.link(source)

    result_image = image_data.create_image_edit_result(
        source_image,
        np.zeros(4 * 4 * 4, dtype=np.float32),
        (4, 4),
    )
    result_image = image_data.replace_empty_image(source, result_image)

    assert source.data == result_image
    assert result_image.name == "Poster.png"
    assert bpy.data.images.get("Poster.png") == result_image


def test_mask_frame_mask_extend_preserves_packed_hidden_rgb(monkeypatch):
    from io import BytesIO
    from PIL import Image

    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Frame RGB", width=4, height=4, alpha=True)
    rgba = np.ones((4, 4, 4), dtype=np.float32)
    rgba[..., :3] = np.arange(48).reshape((4, 4, 3)) / 47.0
    source_image.pixels.foreach_set(np.flipud(rgba).ravel())
    source_image.update()
    expected = image_data.image_rgba(source_image).copy()
    source = bpy.data.objects.new("Frame RGB", None)
    source.empty_display_type = "IMAGE"
    source.empty_display_size = 2.0
    source.empty_image_offset = (-0.5, -0.5)
    source.data = source_image
    bpy.context.collection.objects.link(source)
    selection = SelectionMask(np.ones((4, 4), dtype=np.float32), (0, 0, 4, 4))
    operator = SimpleNamespace(mode="SUBTRACT", report=lambda *_args: None)
    assert edit_mask.EditImageAlpha._apply_mask(
        operator, SimpleNamespace(), source, selection
    ) == {"FINISHED"}
    result = apply_frame(
        monkeypatch, (source,), ((0, 4), (4, 4), (4, 0), (0, 0)), (4, 4),
    )
    assert not result.is_float and result.colorspace_settings.name == "sRGB"
    assert result.alpha_mode == "STRAIGHT"
    assert source.use_empty_image_alpha
    assert result.packed_file is not None
    packed = np.asarray(Image.open(BytesIO(result.packed_file.data)).convert("RGBA")) / 255.0
    np.testing.assert_allclose(packed[..., :3], expected[..., :3], atol=1 / 255)
    np.testing.assert_array_equal(packed[..., 3], 0)
    result.reload()
    assert result.alpha_mode == "STRAIGHT"
    operator.mode = "EXTEND"
    assert edit_mask.EditImageAlpha._apply_mask(
        operator, SimpleNamespace(), source, selection
    ) == {"FINISHED"}
    restored = image_data.image_rgba(source.data)
    np.testing.assert_allclose(restored[..., :3], expected[..., :3], atol=1 / 255)
    np.testing.assert_array_equal(restored[..., 3], 1)


def test_frame_restored_alpha_keeps_foreground_blended_into_white(monkeypatch):
    from io import BytesIO
    from PIL import Image

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sources = []
    for name, color, depth in (("Background", (1, 1, 1, 0), 2),
                               ("Foreground", (0.2, 0.4, 0.6, 1), 1)):
        image = bpy.data.images.new(name, width=6, height=2, alpha=True)
        rgba = np.tile(color, (2, 6, 1)).astype(np.float32)
        if name == "Foreground":
            rgba[..., 3] = (0, 0.01, 0.1, 0.25, 0.5, 1)
            rgba[:, 0, :3] = 0
        image.pixels.foreach_set(np.flipud(rgba).ravel())
        image.update()
        source = bpy.data.objects.new(name, None)
        source.empty_display_type = "IMAGE"
        source.empty_display_size = 2
        source.empty_image_offset = (-0.5, -0.5)
        source.data = image
        source.matrix_world = Matrix.Translation((0, 0, -depth))
        bpy.context.collection.objects.link(source)
        sources.append(source)
    front = sources[1]
    front_rgba = image_data.image_rgba(front.data)
    source_alpha = front_rgba[..., 3:4]
    expected = linear_rgb_to_srgb(
        srgb_to_linear_rgb(front_rgba[..., :3]) * source_alpha + 1 - source_alpha,
    )
    # The image aspect makes its orthographic screen projection two thirds of a pixel high.
    result = apply_frame(
        monkeypatch, sources, ((0, 4 / 3), (6, 4 / 3), (6, 2 / 3), (0, 2 / 3)), (6, 2),
    )
    assert bpy.data.objects.get("Background") is None
    assert front.data == result
    assert not result.is_float and result.colorspace_settings.name == "sRGB"
    encoded = np.asarray(Image.open(BytesIO(result.packed_file.data)).convert("RGBA")) / 255
    np.testing.assert_allclose(encoded[..., :3], expected, atol=1 / 255)
    np.testing.assert_allclose(encoded[..., 3:4], source_alpha, atol=1 / 255)
    selection = SelectionMask(np.ones((2, 6), dtype=np.float32), (0, 0, 6, 2))
    operator = SimpleNamespace(mode="EXTEND", report=lambda *_args: None)
    assert edit_mask.EditImageAlpha._apply_mask(
        operator, SimpleNamespace(), front, selection
    ) == {"FINISHED"}
    restored = image_data.image_rgba(front.data)
    np.testing.assert_allclose(restored[..., :3], expected, atol=1 / 255)
    np.testing.assert_array_equal(restored[..., 3], 1)
    assert np.all(np.diff(restored[0, :, 0]) <= 0)
    np.testing.assert_array_equal(restored[0, 0, :3], 1)


def test_brush_release_commits_one_packed_image_without_touching_shared_source():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Mask Source", width=8, height=6, alpha=True)
    source_rgba = np.ones((6, 8, 4), dtype=np.float32)
    source_rgba[:, :, :3] = (0.2, 0.4, 0.6)
    source_image.pixels.foreach_set(np.flipud(source_rgba).ravel())
    source_image.update()
    source = bpy.data.objects.new("Mask Source", None)
    source.empty_display_type = "IMAGE"
    source.data = source_image
    source.empty_display_size = 3.0
    source.empty_image_offset = (-0.25, -0.75)
    source.matrix_world = Matrix.Translation((1.0, 2.0, 3.0))
    shared = bpy.data.objects.new("Mask Shared", None)
    shared.empty_display_type = "IMAGE"
    shared.data = source_image
    bpy.context.collection.objects.link(source)
    bpy.context.collection.objects.link(shared)
    matrix = source.matrix_world.copy()

    selection_mask = SelectionMask(
        np.ones((2, 3), dtype=np.float32),
        (2, 1, 5, 3),
    )
    operator = SimpleNamespace(mode="SUBTRACT", report=lambda *_args: None)
    status = edit_mask.EditImageAlpha._apply_mask(
        operator,
        SimpleNamespace(),
        source,
        selection_mask,
    )

    result = source.data
    assert status == {"FINISHED"}
    assert source.data == result
    assert result != source_image
    assert result.packed_file is not None
    assert shared.data == source_image
    np.testing.assert_allclose(image_data.image_rgba(source_image), source_rgba)
    result_rgba = image_data.image_rgba(result)
    np.testing.assert_array_equal(result_rgba[1:3, 2:5, 3], 0.0)
    assert source.matrix_world == matrix
    assert source.empty_display_size == 3.0
    assert tuple(source.empty_image_offset) == (-0.25, -0.75)


@pytest.mark.parametrize("cancel", ["ESC", "SWITCH_TOOL"])
def test_cancelled_brush_stroke_releases_preview_and_preserves_shared_image(monkeypatch, cancel):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    source_image = bpy.data.images.new("Mask Cancel", width=4, height=3, alpha=True)
    source = bpy.data.objects.new("Mask Cancel", None)
    source.empty_display_type = "IMAGE"
    source.data = source_image
    bpy.context.collection.objects.link(source)
    image_count = len(bpy.data.images)
    shared = bpy.data.objects.new("Mask Cancel shared", None)
    shared.empty_display_type = "IMAGE"
    shared.data = source_image
    before = np.array(source_image.pixels[:])

    def execute(operator, context):
        operator.gesture, operator.radius = "BRUSH", 5
        operator.source_object_name = source.name
        operator._source_matrix = source.matrix_world.copy()
        operator._path = [(10.0, 10.0)]
        operator._path_samples = list(operator._path)
        event = SimpleNamespace(type="MOUSEMOVE", value="NOTHING", mouse_region_x=20, mouse_region_y=25)
        assert operator.modal(context, event) == {"RUNNING_MODAL"}
        operator._draw_preview((1, 1, 1, 0.16))
        assert operator._brush_preview.coverage
        if cancel == "SWITCH_TOOL":
            monkeypatch.setattr(image_gesture, "active_view3d_tool_id", lambda _: "builtin.select")
        else:
            event.type, event.value = "ESC", "PRESS"
        result = operator.modal(context, event)
        assert operator._path is operator._path_samples is operator._brush_preview is None
        return result

    monkeypatch.setattr(image_gesture, "active_view3d_tool_id", lambda _: edit_mask.MASK_TOOL_ID)
    monkeypatch.setattr(edit_mask.BrushPreview, "draw", lambda *_: None)
    monkeypatch.setattr(edit_mask.EditImageAlpha, "poll", classmethod(lambda cls, context: True))
    monkeypatch.setattr(edit_mask.EditImageAlpha, "execute", execute, raising=False)
    bpy.utils.register_class(edit_mask.EditImageAlpha)
    try:
        area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
        with bpy.context.temp_override(area=area):
            assert bpy.ops.anyimage.edit_image_alpha() == {"CANCELLED"}
    finally:
        bpy.utils.unregister_class(edit_mask.EditImageAlpha)
    assert source.data == shared.data == source_image
    np.testing.assert_array_equal(source_image.pixels[:], before)
    assert len(bpy.data.images) == image_count
