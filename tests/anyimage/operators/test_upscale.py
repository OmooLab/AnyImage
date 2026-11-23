from types import SimpleNamespace
from unittest.mock import patch

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common.image import image_pixels
from anyimage.common.image_target import ImageEditTarget
from anyimage.operators.upscale import UpscaleImage, upscale_output_format
from tests.support.blender import BlenderTestCase


class UpscaleOperatorTest(BlenderTestCase):
    def test_upscale_operator_opens_setup_when_required_ai_is_missing(self):
        expected = {"CANCELLED"}
        operator = self.upscale.UpscaleImage()
        with patch.object(
            self.upscale,
            "invoke_ai_setup_if_needed",
            return_value=expected,
        ) as setup:
            result = operator.invoke(None, None)

        setup.assert_called_once_with(operator)
        self.assertIs(result, expected)

    def test_upscale_operator_runs_immediately_when_ai_is_ready(self):
        operator = self.upscale.UpscaleImage()
        context = object()
        expected = {"FINISHED"}
        with (
            patch.object(
                self.upscale,
                "invoke_ai_setup_if_needed",
                return_value=None,
            ),
            patch.object(
                operator,
                "execute",
                return_value=expected,
            ) as execute,
        ):
            result = operator.invoke(context, None)

        execute.assert_called_once_with(context)
        self.assertIs(result, expected)
        self.assertNotIn("REGISTER", operator.bl_options)


@pytest.mark.parametrize("shared,floating", [(False, False), (True, False), (False, True)])
def test_upscale_result_replacement_undo_restores_source(tmp_path, shared, floating):
    source = bpy.data.images.new("Upscale undo source", width=8, height=8, alpha=True, float_buffer=floating)
    source.colorspace_settings.name = "sRGB"
    source.pixels.foreach_set(np.ones(8 * 8 * 4, dtype=np.float32))
    source.pack()
    owner = bpy.data.objects.new("Upscale undo owner", None)
    owner.empty_display_type = "IMAGE"
    owner.data = source
    bpy.context.scene.collection.objects.link(owner)
    other = owner.copy() if shared else None
    if other:
        bpy.context.scene.collection.objects.link(other)
    owner_name, source_name = owner.name, source.name
    other_name = other.name if other else None
    path = tmp_path / "upscale.png"
    Image.new("RGBA", (16, 16), (32, 64, 96, 128)).save(path)
    bpy.context.preferences.edit.use_global_undo = True
    try:
        bpy.ops.ed.undo_push(message="Before Upscale")
        target, _ = ImageEditTarget.capture(SimpleNamespace(object=owner))
        operator = SimpleNamespace(_image_target=target, _output_format=upscale_output_format(source),
                                   _model="HAT_GAN_X4_SHARPER")
        source.alpha_mode = "CHANNEL_PACKED"
        source.pixels[0] = .25
        source.update()
        before = image_pixels(source)

        UpscaleImage.response(operator, bpy.context, SimpleNamespace(file=lambda _: path))
        assert tuple(owner.data.size) == (16, 16)
        assert owner.data.alpha_mode == operator._output_format.alpha_mode
        assert bpy.ops.ed.undo() == {"FINISHED"}
        restored = bpy.data.objects[owner_name].data
        assert tuple(restored.size) == (8, 8)
        assert restored.alpha_mode == "CHANNEL_PACKED" and restored.colorspace_settings.name == "sRGB"
        if floating:
            np.testing.assert_allclose(image_pixels(restored), before, rtol=8e-5, atol=2e-6)
        else:
            np.testing.assert_array_equal(image_pixels(restored), before)
    finally:
        if other_name:
            bpy.data.objects.remove(bpy.data.objects[other_name], do_unlink=True)
        bpy.data.objects.remove(bpy.data.objects[owner_name], do_unlink=True)
        bpy.data.images.remove(bpy.data.images[source_name])
