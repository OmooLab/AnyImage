from unittest.mock import patch
import bpy
import numpy as np
import pytest


from anyimage.common import image, viewport
from anyimage.operators import mask_tool as mask


@pytest.mark.parametrize("gesture", ["LASSO", "BRUSH", "POLYLINE"])
@pytest.mark.parametrize("alpha_mode", ["STRAIGHT", "PREMUL"])
def test_mask_commit_is_one_undo_transaction(gesture, alpha_mode):
    source = bpy.data.images.new("Undo source", width=8, height=8, alpha=True)
    source.alpha_mode = alpha_mode
    source.pixels.foreach_set(np.ones(8 * 8 * 4, dtype=np.float32))
    source.pack()
    owner = bpy.data.objects.new("Mask undo owner", None)
    owner.empty_display_type = "IMAGE"
    owner.data = source
    bpy.context.scene.collection.objects.link(owner)
    shared = bpy.data.objects.new("Mask undo shared", None)
    shared.empty_display_type = "IMAGE"
    shared.data = source
    bpy.context.scene.collection.objects.link(shared)
    owner_name, shared_name, source_name = owner.name, shared.name, source.name
    before = image.image_pixels(source)
    options = mask.EditImageAlpha.bl_options
    assert options == {"UNDO"}

    def execute(operator, context):
        """Drive gesture completion without a window event in background bpy."""
        operator.gesture, operator.mode, operator.radius = gesture, "SUBTRACT", 2
        operator.source_object_name = owner_name
        operator.source_matrix_data = viewport.serialize_matrix(owner.matrix_world)
        operator._path = [(2, 2), (6, 2), (6, 6), (2, 6)]
        operator._path_samples = list(operator._path)
        return operator._complete(context)

    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(mask.EditImageAlpha, "execute", execute, create=True), patch.object(
        mask.EditImageAlpha, "poll", classmethod(lambda cls, context: True)
    ), patch.object(viewport, "screen_path_to_image_pixels", side_effect=lambda path, *args, **kwargs: path), patch.object(
        mask, "screen_path_to_image_pixels", side_effect=lambda path, *args, **kwargs: path
    ), patch.object(mask, "create_image_edit_result", wraps=mask.create_image_edit_result) as create:
        bpy.utils.register_class(mask.EditImageAlpha)
        try:
            bpy.ops.ed.undo_push(message="Before Mask")
            assert bpy.ops.anyimage.edit_image_alpha("EXEC_DEFAULT", True) == {"FINISHED"}
            create.assert_called_once()
            result = bpy.data.objects[owner_name].data
            assert result.packed_file is not None and result.alpha_mode == alpha_mode
            assert bpy.data.objects[shared_name].data.name == source_name
            np.testing.assert_array_equal(image.image_pixels(bpy.data.images[source_name]), before)
            assert bpy.ops.ed.undo() == {"FINISHED"}
            assert bpy.data.objects[owner_name].data.name == source_name
            assert bpy.data.objects[owner_name].data.alpha_mode == alpha_mode
            np.testing.assert_array_equal(image.image_pixels(bpy.data.objects[owner_name].data), before)
        finally:
            bpy.utils.unregister_class(mask.EditImageAlpha)
            for name in (owner_name, shared_name):
                obj = bpy.data.objects.get(name)
                if obj is not None:
                    bpy.data.objects.remove(obj, do_unlink=True)
            source = bpy.data.images.get(source_name)
            if source is not None:
                bpy.data.images.remove(source)
