import tempfile
from pathlib import Path
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common import ai
from anyimage.common.image import image_rgba
from anyimage.common.image_target import ImageEditTarget
from anyimage.operators import upscale
from anyimage.operators import depth_plane
from anyimage.operators import remove_background as background
from anyimage.runtime import runtime
from anyimage.server.media.input import load_ai_input
from tests.support.image_texture import texture, texture_context


@pytest.mark.parametrize("space", ["sRGB", "Linear Rec.709", "Display P3", "Non-Color", "AgX Base sRGB"])
def test_three_jobs_submit_the_same_half_transparent_color(texture, monkeypatch, space):
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
            np.testing.assert_array_equal(load_ai_input(path, as_bytes=True)[0, 0], (128, 64, 26, 128))
        for snapshot in snapshots[1:]:
            np.testing.assert_array_equal(snapshot, snapshots[0])
    finally:
        for operation, state in operations:
            operation.cleanup(state)


def test_inverse_material_edits_roundtrip_source_samples(texture, tmp_path, monkeypatch):
    image = texture.image
    image.colorspace_settings.name = "AgX Base sRGB"
    image.alpha_mode = "STRAIGHT"
    swatches = np.array([[34, 20, 80, 0], [96, 96, 96, 128], [245, 172, 36, 255], [255, 255, 255, 255]], np.uint8)
    original = np.tile(swatches, (3, 1, 1))
    image.pixels.foreach_set((original[::-1].astype(np.float32) / 255).ravel())
    context = texture_context(texture)
    state = SimpleNamespace(_input_path=None)
    monkeypatch.setattr(upscale, "model_job_parameters", lambda _: {})
    try:
        request = upscale.UpscaleImage.request(state, context)
        submitted = load_ai_input(request["input"], as_bytes=True)
        np.testing.assert_array_equal(submitted, original)
        doubled = submitted.repeat(2, axis=0).repeat(2, axis=1)
        output = tmp_path / "upscale.png"
        Image.fromarray(doubled).save(output)
        upscale.apply_upscale_result(state._image_target, output)
    finally:
        upscale.UpscaleImage.cleanup(state)
    image.reload()
    assert image.colorspace_settings.name == "AgX Base sRGB" and image.alpha_mode == "STRAIGHT"
    np.testing.assert_array_equal(np.rint(image_rgba(image) * 255), doubled)

    target, rgba = ImageEditTarget.capture(context)
    snapshot = background.BackgroundInput.prepare(image, rgba)
    try:
        mask = np.ones(rgba.shape[:2], np.float32)
        mask[:, 2:5] = 0
        alpha_path = tmp_path / "mask.npy"
        np.save(alpha_path, mask)
        snapshot.apply(target, alpha_path)
    finally:
        background.cleanup_image_input(snapshot.path)
    image.reload()
    assert image.colorspace_settings.name == "AgX Base sRGB" and image.alpha_mode == "STRAIGHT"
    doubled[..., 3] *= mask.astype(np.uint8)
    np.testing.assert_array_equal(np.rint(image_rgba(image) * 255), doubled)


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


@pytest.mark.parametrize("space,gray", [("sRGB", 128), ("Linear Rec.709", 128), ("AgX Base sRGB", 128)])
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
        doubled = snapshot.repeat(2, axis=0).repeat(2, axis=1)
        output = tmp_path / "upscale.png"
        Image.fromarray(doubled).save(output)
        upscale.apply_upscale_result(operation._image_target, output)
        image.reload()
        assert image.is_float and image.colorspace_settings.name == space
        upscale.UpscaleImage.cleanup(operation)
        again = upscale.UpscaleImage.request(operation, bpy.context)
        np.testing.assert_array_equal(load_ai_input(again["input"], as_bytes=True), doubled)
        image.pixels[0] = 2
        image.update()
        with pytest.raises(ValueError, match="non-HDR"):
            upscale.UpscaleImage.request(operation, bpy.context)
    finally:
        upscale.UpscaleImage.cleanup(operation)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)


def test_remove_background_keeps_16bit_inverse_source_samples(texture, tmp_path):
    from anyimage.common.color_image import save_float_png

    rgba = np.array([[[.18, .45, .83, .5], [.9, .4, .2, 1]]], np.float32)
    path = tmp_path / "source16.png"
    save_float_png(rgba, path)
    image = bpy.data.images.load(str(path))
    image.colorspace_settings.name = "AgX Base sRGB"
    image.alpha_mode = "STRAIGHT"
    texture.image = image
    target, pixels = ImageEditTarget.capture(texture_context(texture))
    snapshot = background.BackgroundInput.prepare(image, pixels)
    try:
        np.testing.assert_allclose(load_ai_input(snapshot.path), rgba, atol=3e-5)
        mask = np.array([[.5, .75]], np.float32)
        alpha_path = tmp_path / "mask.npy"
        np.save(alpha_path, mask)
        result = snapshot.apply(target, alpha_path)
        result.reload()
        assert result.is_float and result.file_format == "PNG"
        assert result.alpha_mode == "STRAIGHT" and result.colorspace_settings.name == "AgX Base sRGB"
        result.colorspace_settings.name = "Non-Color"
        rgba[..., 3] *= mask
        np.testing.assert_allclose(image_rgba(result), rgba, atol=3e-5)
    finally:
        background.cleanup_image_input(snapshot.path)


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
