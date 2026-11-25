from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.operators.remove_background import BackgroundInput
from anyimage.common.image import image_rgba
from anyimage.common.image_input import cleanup_image_input
from anyimage.common.image_target import ImageEditTarget
from anyimage.operators import remove_background
from tests.support.image_texture import hdr_texture, texture, texture_context


@pytest.mark.parametrize("move_image", [True, False], ids=["image-empty", "other-object"])
def test_undo_move_after_removing_rgb_background(tmp_path, move_image):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.edit.use_global_undo = True
    path = tmp_path / "source.jpg"
    Image.new("RGB", (8, 8), (215, 53, 66)).save(path)
    owner = bpy.data.objects.new("Background removal", None)
    owner.empty_display_type = "IMAGE"
    owner.data = bpy.data.images.load(str(path))
    other = bpy.data.objects.new("Other", None)
    for obj in (owner, other):
        bpy.context.collection.objects.link(obj)
    owner.select_set(True)
    bpy.context.view_layer.objects.active = owner
    owner_name = owner.name
    mask = np.ones((8, 8), dtype=np.float32)
    mask[:, :4] = 0
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, mask)
    try:
        bpy.ops.ed.undo_push(message="Original image")
        target, rgba = ImageEditTarget.capture(bpy.context)
        operator = SimpleNamespace(
            _image_target=target, _background_input=BackgroundInput.prepare(owner.data, rgba),
        )
        result = SimpleNamespace(file=lambda _: alpha_path)
        try:
            remove_background.RemoveImageBackground.response(operator, bpy.context, result)
        finally:
            remove_background.RemoveImageBackground.cleanup(operator)
        np.testing.assert_array_equal(image_rgba(owner.data)[..., 3], mask)

        moved = owner if move_image else other
        moved_name = moved.name
        owner.select_set(move_image)
        moved.select_set(True)
        bpy.context.view_layer.objects.active = moved
        assert bpy.ops.transform.translate("EXEC_DEFAULT", True, value=(2, 0, 0)) == {"FINISHED"}
        assert moved.location.x == 2
        assert bpy.ops.ed.undo() == {"FINISHED"}
        assert bpy.data.objects[moved_name].location.x == 0
        np.testing.assert_array_equal(image_rgba(bpy.data.objects[owner_name].data)[..., 3], mask)
        assert bpy.ops.ed.undo() == {"FINISHED"}
        np.testing.assert_array_equal(image_rgba(bpy.data.objects[owner_name].data), rgba)
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("owner_kind,shared", [("texture", False), ("empty", True)])
def test_hdr_background_undo_redo(hdr_texture, tmp_path, owner_kind, shared):
    node = hdr_texture
    source = node.image
    before = image_rgba(source).copy()
    if owner_kind == "empty":
        owner = bpy.data.objects.new("HDR Empty", None)
        owner.empty_display_type = "IMAGE"
        owner.data = source
        bpy.context.scene.collection.objects.link(owner)
        node.image = source if shared else None
    elif shared:
        other = node.id_data.nodes.new("ShaderNodeTexImage")
        other.image = source
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, np.full((3, 4), 0.37123, np.float32))

    def current_owner():
        if owner_kind == "empty":
            return bpy.data.objects["HDR Empty"]
        return bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]

    def current_image():
        owner = current_owner()
        return owner.data if owner_kind == "empty" else owner.image

    def execute(operator, context):
        owner = current_owner()
        target_context = SimpleNamespace(object=owner, space_data=None) if owner_kind == "empty" else texture_context(owner)
        operator._image_target, rgba = ImageEditTarget.capture(target_context)
        operator._background_input = BackgroundInput.prepare(operator._image_target.image, rgba)
        try:
            operator.response(context, SimpleNamespace(file=lambda key: alpha_path))
        finally:
            operator.cleanup()
        return {"FINISHED"}

    operation = remove_background.RemoveImageBackground
    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(operation, "execute", execute), patch.object(operation, "poll", classmethod(lambda cls, context: True), create=True):
        bpy.utils.register_class(operation)
        try:
            bpy.ops.ed.undo_push(message="Before HDR removal")
            assert bpy.ops.anyimage.remove_image_background("EXEC_DEFAULT", True) == {"FINISHED"}
            after = image_rgba(current_image()).copy()
            np.testing.assert_array_equal(after[..., :3], before[..., :3] * np.float32(0.37123))
            np.testing.assert_allclose(after[..., 3], before[..., 3] * np.float32(0.37123), atol=1e-7)
            assert bpy.ops.ed.undo() == {"FINISHED"}
            np.testing.assert_array_equal(image_rgba(current_image()), before)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            np.testing.assert_array_equal(image_rgba(current_image()), after)
            assert current_image().is_float
        finally:
            bpy.utils.unregister_class(operation)


@pytest.mark.parametrize("outcome", ["cancel", "raise"])
def test_hdr_submission_failure_releases_preview_and_snapshot(hdr_texture, outcome):
    capture = ImageEditTarget.capture(texture_context(hdr_texture))
    paths = []
    operation = remove_background.RemoveImageBackground
    original_cleanup = operation.cleanup
    original_execute = operation.execute
    context = SimpleNamespace(window_manager=Mock(), window=None)

    def execute(operator, _context):
        result = original_execute(operator, context)
        if result == {"RUNNING_MODAL"}:
            runtime._tick()
            return operator.modal(context, SimpleNamespace(type="TIMER"))
        return result

    def cleanup(operator):
        paths.append(operator._background_input.path)
        assert paths[-1].is_file()
        original_cleanup(operator)

    from anyimage.runtime import runtime
    with (
        patch.object(ImageEditTarget, "capture", return_value=capture),
        patch.object(runtime, "can_submit", return_value=outcome == "raise"),
        patch.object(runtime, "enable"),
        patch.object(runtime.server, "poll"),
        patch.object(runtime.server, "submit", side_effect=RuntimeError("Submission failed")),
        patch.object(operation, "execute", execute),
        patch.object(operation, "poll", classmethod(lambda cls, context: True)),
        patch.object(remove_background, "model_job_parameters", return_value={}),
        patch.object(operation, "cleanup", cleanup),
    ):
        bpy.utils.register_class(operation)
        try:
            message = "Submission failed" if outcome == "raise" else "Cannot submit"
            with pytest.raises(RuntimeError, match=message):
                bpy.ops.anyimage.remove_image_background("EXEC_DEFAULT")
        finally:
            bpy.utils.unregister_class(operation)
    assert len(paths) == 1 and not paths[0].parent.exists()
    assert not runtime.jobs


def test_hdr_request_uses_alpha_output_and_current_still(hdr_texture):
    operation = remove_background.RemoveImageBackground
    operator = SimpleNamespace(_input_path=None)
    try:
        with patch.object(remove_background, "model_job_parameters", return_value={}):
            parameters = operation.request(operator, texture_context(hdr_texture))
        assert Path(parameters["input"]).is_file()
        assert "start_frame" not in parameters and "video_frames" not in parameters
    finally:
        cleanup_image_input(operator._background_input.path)


@pytest.mark.parametrize("mode", ["STRAIGHT", "NONE"])
def test_byte_background_mask_keeps_submitted_rgb_after_reload(texture, tmp_path, mode):
    image = texture.image
    image.alpha_mode = mode
    pixels = np.tile(np.array((.2, .5, .8, .6), np.float32), (3, 4, 1))
    pixels[:, 0, 3] = 0
    image.pixels.foreach_set(pixels[::-1].ravel())
    target, submitted = ImageEditTarget.capture(texture_context(texture))
    snapshot = BackgroundInput.prepare(image, submitted)
    alpha = np.linspace(0, 1, 12, dtype=np.float32).reshape(3, 4)
    path = tmp_path / "alpha.npy"
    np.save(path, alpha)
    try:
        result = snapshot.apply(target, path)
        result.reload()
        restored = image_rgba(result)
        np.testing.assert_allclose(restored[..., :3], submitted[..., :3], atol=1 / 255)
        assert result.alpha_mode == mode
        expected = 1 if mode == "NONE" else submitted[..., 3] * alpha
        np.testing.assert_allclose(restored[..., 3], expected, atol=1 / 255)
        if mode == "NONE":
            result.alpha_mode = "STRAIGHT"
            np.testing.assert_allclose(image_rgba(result)[..., 3], submitted[..., 3] * alpha, atol=1 / 255)
    finally:
        cleanup_image_input(snapshot.path)
