from anyimage.operators.remove_background import BackgroundInput
from anyimage.operators.upscale import apply_upscale_result, upscale_output_format
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest

import anyimage
from anyimage import ai_menus as menu
from anyimage.common import ai, image as images
from anyimage.common.image_target import ImageEditTarget, active_texture_node
from anyimage.operators import upscale
from anyimage.operators import remove_background
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


def test_set_color_reference_from_texture(shader_editor):
    from anyimage.operators.color_match import SetColorReference

    node = active_texture_node(shader_editor)
    settings = SimpleNamespace(color_reference=None)
    context = SimpleNamespace(space_data=shader_editor.space_data,
                              scene=SimpleNamespace(anyimage_settings=settings))
    assert SetColorReference.poll(context)
    assert SetColorReference.execute(None, context) == {"FINISHED"}
    assert settings.color_reference == node.image


@pytest.mark.parametrize("node_type", ["ShaderNodeTexEnvironment", "ShaderNodeTexImage"])
def test_world_texture_menu_and_result(texture, node_type, tmp_path):
    world = bpy.data.worlds.new("Texture world")
    world.use_nodes = True
    bpy.context.scene.world = world
    node = world.node_tree.nodes.new(node_type)
    world.node_tree.nodes.active = node
    node.image = texture.image
    context = texture_context(node)
    context.space_data.shader_type = "WORLD"
    context.space_data.id = world
    assert active_texture_node(context) == node
    layout = Mock()
    anyimage.draw_texture_node_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_called_once_with(menu.TextureNodeMenu.bl_idname)
    write_result(tmp_path)
    target, _ = ImageEditTarget.capture(context)
    apply_upscale_result(target, tmp_path / "foreground.png", upscale_output_format(target.image))
    assert tuple(node.image.size) == (8, 6)
    assert tuple(texture.image.size) == (4, 3)


def test_shader_editor_edits_the_shared_material(shader_editor, tmp_path):
    obj = shader_editor.object
    material = obj.active_material
    other = obj.copy()
    bpy.context.collection.objects.link(other)
    node = active_texture_node(shader_editor)

    target, _ = ImageEditTarget.capture(shader_editor)
    apply_upscale_result(target, write_result(tmp_path), upscale_output_format(target.image))

    assert obj.active_material == other.active_material == material
    assert tuple(node.image.size) == (8, 6)


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
    target, _ = ImageEditTarget.capture(context)
    write_result(tmp_path)
    apply_upscale_result(target, tmp_path / "foreground.png", upscale_output_format(target.image))
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
        target.validate_binding()


def test_texture_menu_uses_node_dimensions_and_ai_settings(texture):
    context = texture_context(texture)
    layout = SimpleNamespace(operator=Mock(), separator=Mock(), menu=Mock())
    with patch(
        "anyimage.common.ai.ai_status",
        return_value={"environment_ready": True, "ready": True},
    ):
        menu.TextureNodeMenu.draw(SimpleNamespace(layout=layout), context)
    assert layout.operator_context == "INVOKE_DEFAULT"
    assert [call.args[0] for call in layout.operator.call_args_list] == [
        "anyimage.remove_image_background",
        "anyimage.upscale_image",
        "anyimage.set_color_reference",
        "anyimage.match_color_reference",
        "anyimage.open_ai_environment_settings",
    ]
    assert layout.operator.call_args_list[1].kwargs["text"] == "Upscale (8 × 6)"
    anyimage.draw_texture_node_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_called_once_with(menu.TextureNodeMenu.bl_idname)
    texture.image = None
    layout.menu.reset_mock()
    anyimage.draw_texture_node_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_not_called()


@pytest.mark.parametrize("busy,limit,expected", [(False, 2048, True), (True, 2048, True), (False, 4, False)])
def test_texture_poll_applies_busy_and_size_limits(texture, busy, limit, expected):
    context = texture_context(texture)
    with patch.object(runtime, "state", return_value="PROCESSING" if busy else "IDLE"), patch.object(
        upscale, "configured_max_ai_input_size", return_value=limit,
    ):
        assert upscale.UpscaleImage.poll(context) == expected
        assert remove_background.RemoveImageBackground.poll(context) is True


@pytest.mark.parametrize("operation,filename,shared", [
    (upscale.UpscaleImage, "upscale.png", True),
    (remove_background.RemoveImageBackground, "alpha.npy", False),
])
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
        operator._image_target, rgba = ImageEditTarget.capture(texture_context(node))
        if operation == upscale.UpscaleImage:
            operator._model = "HAT_GAN_X4_SHARPER"
            operator._output_format = upscale.upscale_output_format(operator._image_target.image)
        else:
            from anyimage.common.image import ImageFormat
            operator._background_input = BackgroundInput(rgba, ImageFormat.capture(operator._image_target.image), tmp_path / "input.npy")
        operator.response(context, SimpleNamespace(file=lambda key: tmp_path / filename))
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
            if filename == "alpha.npy":
                before, after = source_pixels.reshape(-1, 4), result_pixels.reshape(-1, 4)
                np.testing.assert_array_equal(after[:, :3], before[:, :3])
                np.testing.assert_allclose(after[:, 3], before[:, 3] * 0.5, atol=1 / 255)
            assert tuple(texture.image.size) == ((8, 6) if operation == upscale.UpscaleImage else (4, 3))
            assert bpy.ops.ed.undo() == {"FINISHED"}
            restored = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
            assert restored.image.name == source_name
            assert tuple(restored.image.size) == (4, 3)
            np.testing.assert_array_equal(images.image_pixels(restored.image), source_pixels)
            assert bpy.ops.ed.redo() == {"FINISHED"}
            redone = bpy.data.materials["Texture material"].node_tree.nodes["Source texture"]
            assert tuple(redone.image.size) == ((8, 6) if operation == upscale.UpscaleImage else (4, 3))
            np.testing.assert_array_equal(images.image_pixels(redone.image), result_pixels)
            if shared:
                other = redone.id_data.nodes["Other texture"]
                np.testing.assert_array_equal(images.image_pixels(other.image), source_pixels)
                assert other.image != redone.image
        finally:
            bpy.utils.unregister_class(operation)


@pytest.mark.parametrize("operation,filename,outcome", [
    (upscale.UpscaleImage, "upscale.png", "succeeded"),
    (remove_background.RemoveImageBackground, "alpha.npy", "succeeded"),
    (upscale.UpscaleImage, "upscale.png", "failed"),
    (remove_background.RemoveImageBackground, "alpha.npy", "cancelled"),
    (remove_background.RemoveImageBackground, "alpha.npy", "invalid_target"),
])
def test_texture_job_request_and_completion(texture, tmp_path, operation, filename, outcome):
    context = texture_context(texture)
    context.window = bpy.context.window
    context.window_manager = SimpleNamespace(
        event_timer_add=Mock(return_value=object()),
        event_timer_remove=Mock(), modal_handler_add=Mock(),
    )
    write_result(tmp_path, filename)
    server = SimpleNamespace(
        snapshot={"state": "IDLE"}, poll=Mock(),
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
                stack.enter_context(patch.object(ai, name))
            stack.enter_context(patch.object(ai, "configured_device", return_value="cpu"))
            stack.enter_context(patch.object(runtime, "server", server))
            stack.enter_context(patch.object(runtime, "enable"))
            stack.enter_context(patch.object(runtime._config, "environment_ready", return_value=True))
            stack.enter_context(patch.object(runtime, "redraw_ui"))
            if operation == upscale.UpscaleImage:
                stack.enter_context(patch.object(upscale, "configured_upscale_model", return_value="HAT_GAN_X4_SHARPER"))
                stack.enter_context(patch.object(upscale, "configured_max_ai_input_size", return_value=2048))
            assert original_execute(operator, context) == {"RUNNING_MODAL"}
            job = operator._job
            assert job.id
            kind, parameters = server.submit.call_args.args
            assert kind == operation.job_type
            assert "start_frame" not in parameters and "video_frames" not in parameters
            assert parameters["device"] == "cpu"
            assert parameters["model"] == ("HAT_GAN_X4_SHARPER" if operation == upscale.UpscaleImage else "BIREFNET_LITE")
            if operation == upscale.UpscaleImage:
                assert parameters["max_input_size"] == 2048
            input_path = parameters["input"]
            assert Path(input_path).is_file()
            # Selection changes must not redirect completion.
            other = texture.id_data.nodes.new("ShaderNodeTexImage")
            texture.id_data.nodes.active = other
            if outcome == "invalid_target":
                texture.image = None
                server.status.return_value = {"state": "succeeded", "result": {Path(filename).stem: filename}}
            bpy.ops.ed.undo_push(message="Before asynchronous texture result")
            runtime._tick()
            result = operator.modal(context, SimpleNamespace(type="TIMER"))
            assert result == ({"FINISHED"} if outcome == "succeeded" else {"CANCELLED"})
            assert not runtime.jobs
            assert operator._image_target is None
            assert not Path(input_path).exists()
            assert other.image is None
            if outcome == "succeeded":
                assert tuple(texture.image.size) == ((8, 6) if operation == upscale.UpscaleImage else (4, 3))
            elif outcome != "invalid_target":
                np.testing.assert_array_equal(images.image_pixels(texture.image), original_pixels)
            context.window_manager.event_timer_remove.assert_called_once()
            server.mark_job_complete.assert_called_once_with("texture-job")
            return result

    with patch.object(operation, "execute", execute), patch.object(
        operation, "poll", classmethod(lambda cls, context: True), create=True,
    ):
        bpy.utils.register_class(operation)
        try:
            call = getattr(bpy.ops.anyimage, operation.bl_idname.split(".")[1])
            if outcome in {"failed", "invalid_target"}:
                message = "Server job failed" if outcome == "failed" else "no longer available"
                with pytest.raises(RuntimeError, match=message):
                    call("EXEC_DEFAULT", True)
            else:
                assert call("EXEC_DEFAULT", True) == ({"FINISHED"} if outcome == "succeeded" else {"CANCELLED"})
        finally:
            runtime.disable()
            bpy.utils.unregister_class(operation)
