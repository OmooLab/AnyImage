from types import SimpleNamespace
import bpy
import numpy as np
from mathutils import Matrix


from anyimage.common import image as image_data
from anyimage.common.selection import SelectionMask
from anyimage.operators import mask_tool as edit_mask
from anyimage.operators.frame_tool import operators as edit_frame
from anyimage.operators.frame_tool.compositing import composite_frame_pixels


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


def test_mask_frame_mask_extend_preserves_packed_hidden_rgb():
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
    descriptor = edit_frame._frame_source(
        source, SimpleNamespace(width=4, height=4),
        SimpleNamespace(perspective_matrix=Matrix.Identity(4), is_perspective=False),
        Matrix.Identity(4), active=True,
    )
    np.testing.assert_allclose(descriptor["rgba"][..., :3], expected[..., :3])
    np.testing.assert_array_equal(descriptor["pixels"], 0)
    framed = composite_frame_pixels(
        (descriptor,), ((0, 4), (4, 4), (4, 0), (0, 0)), (4, 4)
    )
    result = image_data.create_image_edit_result(source.data, framed, (4, 4))
    result = image_data.replace_empty_image(source, result)
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


def test_frame_restored_alpha_keeps_foreground_blended_into_white():
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
        sources.append(edit_frame._frame_source(
            source, SimpleNamespace(width=6, height=2),
            SimpleNamespace(perspective_matrix=Matrix.Identity(4), is_perspective=False),
            Matrix.Identity(4), active=name == "Foreground",
        ))
    front = sources[1]
    source_alpha = front["rgba"][..., 3:4]
    expected = front["rgba"][..., :3] * source_alpha + 1 - source_alpha
    # The image aspect makes its orthographic screen projection two thirds of a pixel high.
    pixels = composite_frame_pixels(
        sources, ((0, 4 / 3), (6, 4 / 3), (6, 2 / 3), (0, 2 / 3)), (6, 2)
    )
    result = image_data.create_image_edit_result(front["object"].data, pixels, (6, 2))
    result = image_data.replace_empty_image(front["object"], result)
    encoded = np.asarray(Image.open(BytesIO(result.packed_file.data)).convert("RGBA")) / 255
    np.testing.assert_allclose(encoded[..., :3], expected, atol=1 / 255)
    np.testing.assert_allclose(encoded[..., 3:4], source_alpha, atol=1 / 255)
    selection = SelectionMask(np.ones((2, 6), dtype=np.float32), (0, 0, 6, 2))
    operator = SimpleNamespace(mode="EXTEND", report=lambda *_args: None)
    assert edit_mask.EditImageAlpha._apply_mask(
        operator, SimpleNamespace(), front["object"], selection
    ) == {"FINISHED"}
    restored = image_data.image_rgba(front["object"].data)
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


def test_brush_drag_does_not_create_or_update_an_image():
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
    operator = edit_mask.ImageGesture()
    operator.active_tool_id = "anyimage.mask"
    operator.gesture = "BRUSH"
    operator._path = [(10.0, 10.0)]
    operator._path_samples = list(operator._path)
    operator._cursor = (10.0, 10.0)
    context = SimpleNamespace(area=SimpleNamespace(tag_redraw=lambda: None),
                              workspace=SimpleNamespace(status_text_set=lambda value: None))
    event = SimpleNamespace(
        type="MOUSEMOVE",
        value="NOTHING",
        mouse_region_x=20,
        mouse_region_y=25,
    )

    result = edit_mask.ImageGesture.modal(operator, context, event)

    assert result == {"RUNNING_MODAL"}
    assert source.data == source_image
    assert len(bpy.data.images) == image_count
    event.type, event.value = "ESC", "PRESS"
    assert operator.modal(context, event) == {"CANCELLED"}
    assert source.data == shared.data == source_image
    np.testing.assert_array_equal(source_image.pixels[:], before)
    assert len(bpy.data.images) == image_count
    assert operator._path is operator._path_samples is operator._brush_preview is None
