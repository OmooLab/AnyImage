from types import SimpleNamespace
from unittest.mock import patch
import bpy
import numpy as np
from PIL import Image

from anyimage.operators.upscale import UpscaleImage
from anyimage.common.image import image_pixels
from anyimage.common.image_target import ImageEditTarget


def test_upscale_result_replacement_undo_restores_source(tmp_path):
    source = bpy.data.images.new("Upscale undo source", width=8, height=8, alpha=True)
    source.pixels.foreach_set(np.ones(8*8*4, dtype=np.float32))
    source.pack()
    owner = bpy.data.objects.new("Upscale undo owner", None)
    owner.empty_display_type = "IMAGE"
    owner.data = source
    bpy.context.scene.collection.objects.link(owner)
    owner_name, source_name = owner.name, source.name
    before = image_pixels(source)
    Image.new("RGBA", (16,16), (32,64,96,128)).save(tmp_path / "upscale.png")

    def execute(operator, context):
        operator._image_target = ImageEditTarget.capture(SimpleNamespace(object=owner))
        operator.model = "HAT_GAN_X4_SHARPER"
        operator.response(context, SimpleNamespace(file=lambda key: tmp_path / f"{key}.png"))
        return {"FINISHED"}

    bpy.context.preferences.edit.use_global_undo = True
    with patch.object(UpscaleImage, "execute", execute), patch.object(
        UpscaleImage, "poll", classmethod(lambda cls, context: True)
    ):
        bpy.utils.register_class(UpscaleImage)
        try:
            bpy.ops.ed.undo_push(message="Before Upscale")
            assert bpy.ops.anyimage.upscale_image("EXEC_DEFAULT", True) == {"FINISHED"}
            assert tuple(bpy.data.objects[owner_name].data.size) == (16,16)
            assert bpy.ops.ed.undo() == {"FINISHED"}
            restored = bpy.data.objects[owner_name].data
            assert tuple(restored.size) == (8,8)
            np.testing.assert_array_equal(image_pixels(restored), before)
        finally:
            bpy.utils.unregister_class(UpscaleImage)
            bpy.data.objects.remove(bpy.data.objects[owner_name], do_unlink=True)
            bpy.data.images.remove(bpy.data.images[source_name])
