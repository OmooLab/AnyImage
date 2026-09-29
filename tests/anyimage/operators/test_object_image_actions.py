from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest

from anyimage import menu
from anyimage.common import material as material_data
from anyimage.common.image_target import (
    ImageEditTarget,
    image_edit_owner,
    object_color_texture,
)
from anyimage.operators import remove_background, upscale
from anyimage.operators.color_reference import SetColorReference
from anyimage.runtime import runtime
from tests.support.image_texture import write_result


def _image_object(material, name="Image object"):
    mesh = bpy.data.meshes.new(name)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    obj["o_image_object"] = True
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def _context(obj):
    return SimpleNamespace(
        space_data=SimpleNamespace(type="VIEW_3D"),
        object=obj,
        scene=bpy.context.scene,
    )


def _material(kind="PLAIN", image=None):
    source = SimpleNamespace(name=f"{kind} Source")
    color = image or bpy.data.images.new(f"{kind} Color", width=4, height=3, alpha=True)
    if kind == "PANORAMA":
        return material_data.create_emission_material(source, color), color
    if kind == "DEPTH":
        depth = bpy.data.images.new("Depth", width=4, height=3, alpha=True, float_buffer=True)
        return material_data.create_image_material(
            source,
            color,
            displacement_image=depth,
        ), color
    return material_data.create_image_material(source, color), color


@pytest.mark.parametrize("kind", ["PLAIN", "DEPTH", "PANORAMA"])
def test_marked_object_resolves_generated_material_color(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, color = _material(kind)
    obj = _image_object(material)

    node = object_color_texture(obj)
    assert node is not None and node.image == color
    assert image_edit_owner(_context(obj)) == node
    target = ImageEditTarget.capture(_context(obj))
    assert target.object_owner == obj
    assert target.material == material
    assert target.material_slot == 0
    target.validate()


def test_object_target_rejects_unknown_material_and_never_falls_back():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material = bpy.data.materials.new("Unknown")
    material.use_nodes = True
    tree = material.node_tree
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.new("Unknown Color", width=4, height=3)
    tree.links.new(texture.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    obj = _image_object(material)

    context = _context(obj)
    assert object_color_texture(obj) is None
    assert image_edit_owner(context) is None
    with pytest.raises(RuntimeError, match="Select an Image Empty or a material Image Texture"):
        ImageEditTarget.capture(context)


def test_object_target_rejects_changed_material_slot():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, _color = _material()
    obj = _image_object(material)
    target = ImageEditTarget.capture(_context(obj))
    replacement, _replacement_color = _material("PANORAMA")
    obj.material_slots[0].material = replacement

    with pytest.raises(RuntimeError, match="no longer available"):
        target.validate()


def test_object_commit_isolates_shared_material():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, source = _material()
    first = _image_object(material, "First")
    second = _image_object(material, "Second")
    target = ImageEditTarget.capture(_context(first))
    result = bpy.data.images.new("Result", width=8, height=6, alpha=True)
    result.pixels.foreach_set(
        np.tile((0.8, 0.4, 0.2, 0.5), 48).astype(np.float32)
    )

    committed = target.commit(result)

    assert first.active_material != material
    assert second.active_material == material
    assert object_color_texture(first).image == committed
    assert object_color_texture(second).image == source
    assert tuple(committed.size) == (8, 6)
    assert tuple(source.size) == (4, 3)


def test_object_commit_isolates_shared_image():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, source = _material()
    obj = _image_object(material)
    other = bpy.data.objects.new("Other", None)
    other.empty_display_type = "IMAGE"
    other.data = source
    bpy.context.collection.objects.link(other)
    target = ImageEditTarget.capture(_context(obj))
    result = bpy.data.images.new("Result", width=8, height=6, alpha=True)

    committed = target.commit(result)

    assert object_color_texture(obj).image == committed
    assert committed != source
    assert other.data == source
    assert tuple(source.size) == (4, 3)


@pytest.mark.parametrize(
    "operation,filename",
    [
        (upscale.UpscaleImage, "upscale.png"),
        (remove_background.RunBackgroundRemoval, "foreground.png"),
    ],
)
def test_object_action_undo_redo_restores_shared_material(
    tmp_path,
    operation,
    filename,
):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, source = _material()
    first = _image_object(material, "First")
    second = _image_object(material, "Second")
    source_pixels = np.asarray(source.pixels[:], dtype=np.float32)
    write_result(tmp_path, filename)

    def execute(operator, context):
        current = bpy.data.objects["First"]
        operator._image_target = ImageEditTarget.capture(_context(current))
        if operation == upscale.UpscaleImage:
            operator.model = "HAT_GAN_X4_SHARPER"
        operator.response(
            context,
            SimpleNamespace(file=lambda key: tmp_path / f"{key}.png"),
        )
        return {"FINISHED"}

    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(operation, "execute", execute), patch.object(
        operation,
        "poll",
        classmethod(lambda cls, context: True),
        create=True,
    ):
        bpy.utils.register_class(operation)
        try:
            bpy.ops.ed.undo_push(message="Before object processing")
            call = getattr(bpy.ops.anyimage, operation.bl_idname.split(".")[1])
            assert call("EXEC_DEFAULT", True) == {"FINISHED"}
            first = bpy.data.objects["First"]
            second = bpy.data.objects["Second"]
            assert first.active_material != second.active_material
            assert tuple(object_color_texture(first).image.size) == (8, 6)
            assert tuple(object_color_texture(second).image.size) == (4, 3)

            assert bpy.ops.ed.undo() == {"FINISHED"}
            first = bpy.data.objects["First"]
            second = bpy.data.objects["Second"]
            assert first.active_material == second.active_material
            np.testing.assert_array_equal(
                np.asarray(object_color_texture(first).image.pixels[:]),
                source_pixels,
            )

            assert bpy.ops.ed.redo() == {"FINISHED"}
            first = bpy.data.objects["First"]
            second = bpy.data.objects["Second"]
            assert first.active_material != second.active_material
            assert tuple(object_color_texture(first).image.size) == (8, 6)
            assert tuple(object_color_texture(second).image.size) == (4, 3)
        finally:
            bpy.utils.unregister_class(operation)


def test_object_menu_and_operator_polls_use_marked_object():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, _color = _material()
    obj = _image_object(material)
    context = _context(obj)
    layout = SimpleNamespace(operator=Mock(), separator=Mock(), menu=Mock())

    menu.draw_image_object_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_called_once_with(menu.AnyImageObjectMenu.bl_idname, icon="PLUGIN")
    layout.menu.reset_mock()
    obj["o_image_object"] = False
    menu.draw_image_object_context_menu(SimpleNamespace(layout=layout), context)
    layout.menu.assert_not_called()
    obj["o_image_object"] = True

    layout = SimpleNamespace(operator=Mock(), separator=Mock(), menu=Mock())
    with patch(
        "anyimage.properties.ai_status",
        return_value={"environment_ready": True, "ready": True},
    ):
        menu.AnyImageObjectMenu.draw(SimpleNamespace(layout=layout), context)
    assert [call.args[0] for call in layout.operator.call_args_list] == [
        "anyimage.set_color_reference",
        "anyimage.match_color_reference",
        "anyimage.remove_image_background",
        "anyimage.upscale_image",
        "anyimage.clear_models",
        "anyimage.open_ai_environment_settings",
    ]
    assert layout.operator.call_args_list[3].kwargs["text"] == "Upscale (8 × 6)"

    with patch.object(runtime, "server_busy", return_value=False), patch.object(
        upscale,
        "configured_max_ai_input_size",
        return_value=2048,
    ):
        assert remove_background.RemoveImageBackground.poll(context)
        assert upscale.UpscaleImage.poll(context)


def test_object_color_image_can_be_set_as_reference():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    material, color = _material()
    obj = _image_object(material)
    context = _context(obj)
    context.scene = SimpleNamespace(
        anyimage_settings=SimpleNamespace(color_reference=None),
    )

    assert SetColorReference.poll(context)
    assert SetColorReference.execute(SimpleNamespace(report=Mock()), context) == {"FINISHED"}
    assert context.scene.anyimage_settings.color_reference == color
