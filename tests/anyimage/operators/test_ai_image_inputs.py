import tempfile
from pathlib import Path

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.operators import upscale
from anyimage.operators.remove_background import operators as background
from anyimage.runtime import runtime


@pytest.mark.parametrize("module", [upscale, background], ids=["upscale", "remove_background"])
@pytest.mark.parametrize("edit_in_blender", [False, True], ids=["cached", "unsaved"])
def test_job_submits_visible_pixels_after_external_overwrite(module, tmp_path, monkeypatch, edit_in_blender):
    source = tmp_path / "original.tiff"
    Image.new("RGB", (16, 16), (32, 64, 128)).save(source)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    image = bpy.data.images.load(str(source), check_existing=False)
    assert tuple(image.size) == (16, 16)
    expected = (32, 64, 128, 255)
    if edit_in_blender:
        expected = (64, 128, 32, 128)
        image.pixels.foreach_set(np.tile(np.array(expected, np.float32) / 255, 16 * 16))
        image.update()
    Image.new("RGB", (8, 4), (0, 0, 255)).save(source)
    owner = bpy.data.objects.new("Image to edit", None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.collection.objects.link(owner)
    bpy.context.view_layer.objects.active = owner
    monkeypatch.setattr(runtime, "can_submit", lambda: True)
    monkeypatch.setattr(module, "require_environment", lambda: None)
    monkeypatch.setattr(module, "require_model", lambda _model: None)
    submitted = []

    def submit(job_type, parameters, **kwargs):
        path = Path(parameters["input"])
        with Image.open(path) as snapshot:
            assert snapshot.format == "PNG" and snapshot.size == (16, 16)
            assert snapshot.getpixel((0, 0)) == expected
        submitted.append(path)
        raise RuntimeError("End of submission check")

    monkeypatch.setattr(runtime, "submit", submit)
    classes = ((upscale.UpscaleImage,) if module is upscale else
               (background.RunBackgroundRemoval, background.RemoveImageBackground))
    for cls in classes:
        bpy.utils.register_class(cls)
    try:
        action = getattr(bpy.ops.anyimage, classes[-1].bl_idname.split(".")[1])
        with pytest.raises(RuntimeError, match="End of submission check"):
            action()
        assert len(submitted) == 1 and not submitted[0].parent.exists()
        with Image.open(source) as disk:
            assert disk.size == (8, 4) and disk.getpixel((0, 0)) == (0, 0, 255)
    finally:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)


@pytest.mark.parametrize("kind", ["external", "packed", "generated"])
def test_upscale_is_disabled_for_float_images(tmp_path, monkeypatch, kind):
    from anyimage.common.hdr_image import save_hdr_image

    if kind == "generated":
        image = bpy.data.images.new("HDR", width=4, height=4, float_buffer=True)
    else:
        path = tmp_path / "highlights.exr"
        save_hdr_image(np.full((4, 4, 4), [4, 2, 1, 1], np.float32), path)
        image = bpy.data.images.load(str(path), check_existing=False)
        if kind == "packed":
            image.pack()
    owner = bpy.data.objects.new("HDR to edit", None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.collection.objects.link(owner)
    bpy.context.view_layer.objects.active = owner
    monkeypatch.setattr(runtime, "can_submit", lambda: True)
    bpy.utils.register_class(upscale.UpscaleImage)
    try:
        assert not bpy.ops.anyimage.upscale_image.poll()
        assert background.RemoveImageBackground.poll(bpy.context)
    finally:
        bpy.utils.unregister_class(upscale.UpscaleImage)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)
