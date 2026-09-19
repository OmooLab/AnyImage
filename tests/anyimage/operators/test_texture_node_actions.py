from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest

from anyimage import menu
from anyimage.common import image as images
from anyimage.common.image_target import ImageEditTarget, active_texture_node
from anyimage.operators import remove_background, upscale
from anyimage.runtime import runtime
from tests.support.image_texture import texture, texture_context, write_result


@pytest.fixture
def shader_editor(texture):
    mesh = bpy.data.meshes.new("Material owner")
    obj = bpy.data.objects.new("Material owner", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bpy.data.materials["Texture material"])
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    area.type = "NODE_EDITOR"
    area.ui_type = "ShaderNodeTree"
    with bpy.context.temp_override(area=area):
        yield bpy.context


def test_shader_editor_pin_and_shared_group_target(shader_editor, tmp_path):
    context = shader_editor
    node = active_texture_node(context)
    assert node is not None
    assert context.space_data.id == bpy.data.materials["Texture material"]
    context.space_data.pin = True
    bpy.context.view_layer.objects.active = None
    assert active_texture_node(context) == node
    # Use Blender's own grouping operation to exercise nested editor context.
    for candidate in node.id_data.nodes:
        candidate.select = candidate == node
    assert bpy.ops.node.group_make() == {"FINISHED"}
    nested = active_texture_node(context)
    assert nested is not None
    assert context.space_data.edit_tree != context.space_data.node_tree
    group = nested.id_data
    second_instance = context.space_data.node_tree.nodes.new("ShaderNodeGroup")
    second_instance.node_tree = group
    source = nested.image
    target = ImageEditTarget.capture(context)
    write_result(tmp_path)
    target.apply(tmp_path / "foreground.png")
    assert nested.image == source
    assert tuple(source.size) == (8, 6)
    assert second_instance.node_tree.nodes[nested.name].image == source


def test_linked_material_target_is_unavailable(texture, tmp_path):
    path = str(tmp_path / "linked.blend")
    bpy.data.libraries.write(path, {bpy.data.materials["Texture material"]})
    with bpy.data.libraries.load(path, link=True) as (source, destination):
        destination.materials = source.materials
    linked = destination.materials[0].node_tree.nodes["Source texture"]
    context = texture_context(linked)
    assert active_texture_node(context) is None
    target = ImageEditTarget(linked, linked.image, linked.id_data)
    with pytest.raises(RuntimeError, match="no longer available"):
        target.validate()


def test_texture_menu_uses_node_dimensions_and_ai_settings(texture):
    context = texture_context(texture)
    layout = SimpleNamespace(operator=Mock(), separator=Mock(), menu=Mock())
    with patch("anyimage.properties.ai_status", return_value={"ready": True}):
        menu.AnyImageTextureNodeMenu.draw(SimpleNamespace(layout=layout), context)
    assert layout.operator_context == "INVOKE_DEFAULT"
    assert [call.args[0] for call in layout.operator.call_args_list] == [
        "anyimage.remove_image_background", "anyimage.upscale_image", "anyimage.open_ai_environment_settings",
    ]
    assert layout.operator.call_args_list[1].kwargs["text"] == "Upscale (8 × 6)"
    menu.draw_texture_node_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_called_once_with(menu.AnyImageTextureNodeMenu.bl_idname, text="AnyImage", icon="PLUGIN")
    texture.image = None
    layout.menu.reset_mock()
    menu.draw_texture_node_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_not_called()


@pytest.mark.parametrize("busy,limit,expected", [(False, 2048, True), (True, 2048, False), (False, 4, False)])
def test_texture_poll_applies_busy_and_size_limits(texture, busy, limit, expected):
    context = texture_context(texture)
    with patch.object(runtime, "server_busy", return_value=busy), patch.object(
        upscale, "configured_max_ai_input_size", return_value=limit,
    ):
        assert upscale.UpscaleImage.poll(context) == expected
        assert remove_background.RemoveImageBackground.poll(context) == (not busy)


@pytest.mark.parametrize("operation,filename", [(upscale.UpscaleImage, "upscale.png"), (remove_background.RunBackgroundRemoval, "foreground.png")])
@pytest.mark.parametrize("shared", [False, True])
def test_texture_action_undo_redo_restores_image_and_binding(texture, tmp_path, operation, filename, shared):
    source_name = texture.image.name
    source_pixels = images.image_pixels(texture.image)
    if shared:
        other = texture.id_data.nodes.new("ShaderNodeTexImage")
        other.image = texture.image
        other.name = "Other texture"
    write_result(tmp_path, filename)

    def execute(operator, context):
        node = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
        operator._image_target = ImageEditTarget.capture(texture_context(node))
        if operation == upscale.UpscaleImage:
            operator.model = "HAT_GAN_X4_SHARPER"
        operator.response(context, SimpleNamespace(file=lambda key: tmp_path / f"{key}.png"))
        return {"FINISHED"}

    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(operation, "execute", execute), patch.object(
        operation, "poll", classmethod(lambda cls, context: True), create=True,
    ):
        bpy.utils.register_class(operation)
        try:
            bpy.ops.ed.undo_push(message="Before texture processing")
            call = getattr(bpy.ops.anyimage, operation.bl_idname.split(".")[1])
            assert call("EXEC_DEFAULT", True) == {"FINISHED"}
            result_pixels = images.image_pixels(texture.image)
            assert tuple(texture.image.size) == (8, 6)
            assert bpy.ops.ed.undo() == {"FINISHED"}
            restored = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
            assert restored.image.name == source_name
            assert tuple(restored.image.size) == (4, 3)
            np.testing.assert_array_equal(images.image_pixels(restored.image), source_pixels)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            redone = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
            assert tuple(redone.image.size) == (8, 6)
            np.testing.assert_array_equal(images.image_pixels(redone.image), result_pixels)
            if shared:
                other = redone.id_data.nodes["Other texture"]
                np.testing.assert_array_equal(images.image_pixels(other.image), source_pixels)
                assert other.image != redone.image
        finally:
            bpy.utils.unregister_class(operation)


@pytest.mark.parametrize("operation,module,filename", [
    (upscale.UpscaleImage, upscale, "upscale.png"),
    (remove_background.RunBackgroundRemoval, remove_background, "foreground.png"),
])
@pytest.mark.parametrize("outcome", ["succeeded", "cancelled", "failed", "invalid_target"])
def test_texture_job_request_and_completion(texture, tmp_path, operation, module, filename, outcome):
    context = texture_context(texture)
    context.window = object()
    context.window_manager = SimpleNamespace(
        progress_begin=Mock(), progress_end=Mock(), event_timer_add=Mock(return_value=object()),
        event_timer_remove=Mock(), modal_handler_add=Mock(),
    )
    write_result(tmp_path, filename)
    controller = SimpleNamespace(
        submit=Mock(return_value={"job_id": "texture-job", "directory": str(tmp_path)}),
        status=Mock(return_value={"state": "failed" if outcome == "invalid_target" else outcome,
                                  "result": {Path(filename).stem: filename}}),
        mark_job_complete=Mock(), cancel=Mock(),
    )
    original_pixels = images.image_pixels(texture.image)
    original_execute = operation.execute

    def execute(operator, _context):
        with ExitStack() as stack:
            for name in ("require_environment", "require_model"):
                stack.enter_context(patch.object(module, name))
            stack.enter_context(patch.object(module, "production_device", return_value="CPU"))
            stack.enter_context(patch.object(operation, "controller", return_value=controller))
            stack.enter_context(patch.object(runtime, "update_ui"))
            stack.enter_context(patch.object(runtime, "redraw_ui"))
            if operation == upscale.UpscaleImage:
                stack.enter_context(patch.object(upscale, "configured_upscale_model", return_value="HAT_GAN_X4_SHARPER"))
                stack.enter_context(patch.object(upscale, "configured_max_ai_input_size", return_value=2048))
            assert original_execute(operator, context) == {"RUNNING_MODAL"}
            job = runtime.active_job
            job.start_thread.join(timeout=5)
            assert not job.start_thread.is_alive()
            kind, parameters = controller.submit.call_args.args
            assert kind == operation.job_type
            assert "start_frame" not in parameters and "video_frames" not in parameters
            assert parameters["device"] == "cpu"
            assert parameters["model"] == ("HAT_GAN_X4_SHARPER" if operation == upscale.UpscaleImage else "BIREFNET_LITE")
            input_path = operator.input_path
            assert operator.delete_input
            # Selection changes must not redirect completion.
            other = texture.id_data.nodes.new("ShaderNodeTexImage")
            texture.id_data.nodes.active = other
            if outcome == "invalid_target":
                texture.image = None
                controller.status.return_value = {"state": "succeeded", "result": {Path(filename).stem: filename}}
            bpy.ops.ed.undo_push(message="Before asynchronous texture result")
            result = operator.modal(context, SimpleNamespace(type="TIMER"))
            assert result == ({"FINISHED"} if outcome == "succeeded" else {"CANCELLED"})
            assert runtime.active_job is None
            assert operator._image_target is None
            assert not Path(input_path).exists()
            assert other.image is None
            if outcome == "succeeded":
                assert tuple(texture.image.size) == (8, 6)
            elif outcome != "invalid_target":
                np.testing.assert_array_equal(images.image_pixels(texture.image), original_pixels)
            context.window_manager.event_timer_remove.assert_called_once()
            return result

    with patch.object(operation, "execute", execute), patch.object(
        operation, "poll", classmethod(lambda cls, context: True), create=True,
    ):
        bpy.utils.register_class(operation)
        try:
            call = getattr(bpy.ops.anyimage, operation.bl_idname.split(".")[1])
            if outcome in {"failed", "invalid_target"}:
                message = "Server task failed" if outcome == "failed" else "no longer available"
                with pytest.raises(RuntimeError, match=message):
                    call("EXEC_DEFAULT", True)
            else:
                assert call("EXEC_DEFAULT", True) == ({"FINISHED"} if outcome == "succeeded" else {"CANCELLED"})
        finally:
            runtime.close_active()
            bpy.utils.unregister_class(operation)
