import tempfile
from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import ai
from anyimage.operators import upscale
from anyimage.operators import depth_plane
from anyimage.operators import remove_background as background
from anyimage.runtime import runtime
from anyimage.server.media.input import load_ai_input
from tests.support.image_texture import texture, texture_context


@pytest.mark.parametrize("space,expected", [
    ("sRGB", (128, 64, 26)), ("Linear Rec.709", (188, 137, 90)),
    ("Display P3", (138, 59, 10)), ("Non-Color", (128, 64, 26)),
])
def test_three_jobs_submit_the_same_half_transparent_color(texture, monkeypatch, space, expected):
    image = texture.image
    image.colorspace_settings.name = space
    image.alpha_mode = "STRAIGHT"
    image.pixels.foreach_set(np.tile(np.array([.5, .25, .1, .5], np.float32), 12))
    context = texture_context(texture)
    for module in (background, upscale):
        monkeypatch.setattr(module, "model_job_parameters", lambda _: {})
    monkeypatch.setattr(depth_plane, "geometry_job_parameters", lambda _: {})
    operations = (
        (background.RemoveImageBackground, SimpleNamespace(_background_input=None)),
        (upscale.UpscaleImage, SimpleNamespace(_input_path=None)),
        (depth_plane.DepthPlaneJob, SimpleNamespace(_source_image=image, plane_type="DEPTH", _input_path=None)),
    )
    snapshots = []
    try:
        for operation, state in operations:
            path = operation.request(state, context)["input"]
            snapshots.append(np.load(path))
            np.testing.assert_array_equal(load_ai_input(path, as_bytes=True)[0, 0], (*expected, 128))
        for snapshot in snapshots[1:]:
            np.testing.assert_array_equal(snapshot, snapshots[0])
    finally:
        for operation, state in operations:
            operation.cleanup(state)


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
    monkeypatch.setattr(ai, "require_environment", lambda: None)
    monkeypatch.setattr(ai, "require_model", lambda _model: None)
    submitted = []

    def submit(job_type, parameters, **kwargs):
        path = Path(parameters["input"])
        snapshot = np.load(path)
        assert path.suffix == ".npy" and snapshot.shape == (16, 16, 4)
        np.testing.assert_array_equal(snapshot[0, 0], expected)
        submitted.append(path)
        raise RuntimeError("End of submission check")

    monkeypatch.setattr(runtime, "submit", submit)
    cls = upscale.UpscaleImage if module is upscale else background.RemoveImageBackground
    bpy.utils.register_class(cls)
    try:
        action = getattr(bpy.ops.anyimage, cls.bl_idname.split(".")[1])
        with pytest.raises(RuntimeError, match="End of submission check"):
            action()
        assert len(submitted) == 1 and not submitted[0].parent.exists()
        with Image.open(source) as disk:
            assert disk.size == (8, 4) and disk.getpixel((0, 0)) == (0, 0, 255)
    finally:
        bpy.utils.unregister_class(cls)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)


@pytest.mark.parametrize("operation", [background.RemoveImageBackground, upscale.UpscaleImage])
def test_missing_model_stops_before_image_capture(operation, monkeypatch):
    from unittest.mock import Mock

    capture = Mock()
    monkeypatch.setattr(background.ImageEditTarget, "capture", capture)
    monkeypatch.setattr(ai, "require_environment", lambda: None)
    monkeypatch.setattr(ai, "require_model", Mock(side_effect=RuntimeError("Download model first")))
    with pytest.raises(RuntimeError, match="Download model first"):
        operation.request(SimpleNamespace(), bpy.context)
    capture.assert_not_called()


@pytest.mark.parametrize("space,gray", [("sRGB", 128), ("Linear Rec.709", 188)])
def test_upscale_accepts_16bit_sdr_and_rejects_out_of_range_edits(tmp_path, monkeypatch, space, gray):

    path = tmp_path / "gray16.png"
    levels = np.full((4, 4), 128 * 257, np.uint16)
    levels[:, 1] = 65535
    Image.fromarray(levels).save(path)
    image = bpy.data.images.load(str(path))
    image.colorspace_settings.name = space
    owner = bpy.data.objects.new("16-bit source", None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.collection.objects.link(owner)
    bpy.context.view_layer.objects.active = owner
    monkeypatch.setattr(runtime, "can_submit", lambda: True)
    monkeypatch.setattr(upscale, "model_job_parameters", lambda _: {})
    operation = SimpleNamespace(_input_path=None)
    try:
        assert image.is_float and upscale.UpscaleImage.poll(bpy.context)
        parameters = upscale.UpscaleImage.request(operation, bpy.context)
        snapshot = load_ai_input(parameters["input"], as_bytes=True)
        np.testing.assert_array_equal(snapshot[0, 0], (gray, gray, gray, 255))
        np.testing.assert_array_equal(snapshot[0, 1], (255, 255, 255, 255))
        image.pixels[0] = 2
        image.update()
        with pytest.raises(ValueError, match="non-HDR"):
            upscale.UpscaleImage.request(operation, bpy.context)
    finally:
        upscale.UpscaleImage.cleanup(operation)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)


@pytest.mark.parametrize("kind", ["external", "packed", "generated"])
def test_upscale_is_disabled_for_hdr_images(tmp_path, monkeypatch, kind):
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
