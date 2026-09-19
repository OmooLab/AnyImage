from types import SimpleNamespace
from unittest.mock import patch
import bpy
import numpy as np
import pytest
from PIL import Image


from anyimage.common import image as images
from tests.support.color_image import color_image


@pytest.mark.parametrize("floating", [False, True])
def test_owned_color_images_preserve_source_and_use_premul(floating):
    original = bpy.data.images.new("Alpha source", width=2, height=2, alpha=True, float_buffer=floating)
    if floating:
        original.alpha_mode = "PREMUL"
    rgba = np.tile(np.array([0.2, 0.4, 0.8, 0.25], dtype=np.float32), (2, 2, 1))
    original.pixels.foreach_set(rgba.ravel())
    source = SimpleNamespace(data=original)
    expected = images.image_rgba(original)
    cropped = color_image(source.data, (0, 0, 2, 2), expected)
    edited = images.create_image_edit_result(original, rgba.ravel(), (2, 2))
    try:
        assert original.alpha_mode == ("PREMUL" if floating else "STRAIGHT")
        np.testing.assert_allclose(images.image_rgba(original), expected)
        assert edited.alpha_mode == original.alpha_mode
        for image in (cropped,):
            assert image.alpha_mode == original.alpha_mode
            np.testing.assert_allclose(images.image_rgba(image), expected, atol=1 / 255)
    finally:
        for image in (cropped, edited, original):
            bpy.data.images.remove(image)


def test_job_loader_preserves_edit_alpha_policy(tmp_path):
    rgba = np.array([[[51, 102, 204, 64]]], dtype=np.uint8)
    Image.fromarray(rgba).save(tmp_path / "foreground.png")
    original = bpy.data.images.new("Job source", width=1, height=1, alpha=True)
    result = images.load_image_edit_result(original, tmp_path / "foreground.png")
    try:
        assert result.alpha_mode == "STRAIGHT"
        assert result.packed_file is not None
        assert original.alpha_mode == "STRAIGHT"
    finally:
        bpy.data.images.remove(result)
        bpy.data.images.remove(original)


def test_business_pixels_ignore_premul_read_interpretation():
    original = bpy.data.images.new("Premul read source", width=1, height=1, alpha=True)
    original.alpha_mode = "PREMUL"
    expected = np.array([0.4, 0.25, 0.1, 0.5], dtype=np.float32)
    result = images.create_image_edit_result(original, expected, (1, 1))
    try:
        result.reload()
        interpreted = np.empty(4, dtype=np.float32)
        result.pixels.foreach_get(interpreted)
        assert interpreted[0] > expected[0]
        np.testing.assert_allclose(images.image_pixels(result), expected, atol=1 / 255)
        assert result.alpha_mode == "PREMUL"
    finally:
        bpy.data.images.remove(result)
        bpy.data.images.remove(original)


@pytest.mark.parametrize("dirty", [False, True])
def test_business_read_preserves_shared_packed_source(dirty):
    original = bpy.data.images.new("Read integrity", width=1, height=1, alpha=True)
    original.alpha_mode = "PREMUL"
    result = images.create_image_edit_result(original, np.array([0.2, 0.4, 0.8, 0.25], dtype=np.float32), (1, 1))
    owner = bpy.data.objects.new("Read owner", None)
    owner.empty_display_type = "IMAGE"
    owner.data = result
    try:
        result.reload()
        if dirty:
            result.pixels.foreach_set([0.9, 0.1, 0.3, 0.5])
            result.update()
        before = np.array(result.pixels[:])
        packed = bytes(result.packed_file.data)
        state = (result.alpha_mode, result.is_dirty, result.users)
        count = len(bpy.data.images)
        for _ in range(3):
            pixels = images.image_pixels(result)
            np.testing.assert_allclose(pixels, before if dirty else [0.2, 0.4, 0.8, 0.25], atol=1 / 255)
            np.testing.assert_array_equal(result.pixels[:], before)
            assert (result.alpha_mode, result.is_dirty, result.users) == state
            assert bytes(result.packed_file.data) == packed
            assert owner.data == result
            assert len(bpy.data.images) == count
    finally:
        bpy.data.objects.remove(owner)
        bpy.data.images.remove(result)
        bpy.data.images.remove(original)


@pytest.mark.parametrize("floating", [False, True])
def test_generated_premul_reads_current_pixels(floating):
    source = bpy.data.images.new("Generated read", width=1, height=1, alpha=True, float_buffer=floating)
    try:
        source.alpha_mode = "PREMUL"
        source.pixels.foreach_set([0.2, 0.4, 0.8, 0.25])
        before = np.array(source.pixels[:])
        np.testing.assert_array_equal(images.image_pixels(source), before)
        np.testing.assert_array_equal(source.pixels[:], before)
        assert source.alpha_mode == "PREMUL"
    finally:
        bpy.data.images.remove(source)


@pytest.mark.parametrize("packed,floating,dirty", [
    (False, False, False),
    (True, False, True),
    (False, True, True),
    (True, True, False),
])
def test_file_read_preserves_byte_and_native_float_cache(tmp_path, packed, floating, dirty):
    path = tmp_path / ("source.exr" if floating else "source.png")
    if floating:
        generated = bpy.data.images.new("EXR source", width=1, height=1, alpha=True, float_buffer=True)
        try:
            generated.pixels.foreach_set([0.2, 0.4, 0.8, 0.25])
            generated.file_format = "OPEN_EXR"
            generated.filepath_raw = str(path)
            generated.save()
        finally:
            bpy.data.images.remove(generated)
    else:
        Image.fromarray(np.array([[[51, 102, 204, 64]]], dtype=np.uint8)).save(path)
    source = bpy.data.images.load(str(path), check_existing=False)
    try:
        if packed:
            source.pack()
        source.alpha_mode = "PREMUL"
        if dirty:
            source.pixels.foreach_set([0.9, 0.1, 0.3, 0.5])
            source.update()
        before = np.array(source.pixels[:])
        assert source.is_dirty == dirty
        assert source.is_float == floating
        expected = before if floating or dirty else np.array([51, 102, 204, 64]) / 255
        count = len(bpy.data.images)
        np.testing.assert_allclose(images.image_pixels(source), expected, atol=1e-7)
        np.testing.assert_array_equal(source.pixels[:], before)
        assert source.is_dirty == dirty and source.alpha_mode == "PREMUL"
        assert len(bpy.data.images) == count
    finally:
        bpy.data.images.remove(source)


def test_isolated_decode_failure_releases_copy():
    class FailedReader:
        @property
        def alpha_mode(self):
            return "PREMUL"

        @alpha_mode.setter
        def alpha_mode(self, value):
            raise RuntimeError("Decode failed")

    reader = FailedReader()
    source = SimpleNamespace(alpha_mode="PREMUL", is_dirty=False, is_float=False,
                             source="FILE", copy=lambda: reader)
    with patch.object(images, "bpy", SimpleNamespace(data=SimpleNamespace(images=SimpleNamespace(remove=lambda value: removed.append(value))))):
        removed = []
        with pytest.raises(RuntimeError, match="Decode failed"):
            images.image_pixels(source)
    assert removed == [reader]
    assert source.alpha_mode == "PREMUL"


def test_mask_pack_reopen_extend_and_repeat_frame_preserve_hidden_color(tmp_path):
    from anyimage.common.selection import SelectionMask
    from anyimage.operators.mask_tool import apply_alpha_mask
    from anyimage.operators.frame_tool.projection import frame_source_projection
    from anyimage.operators.frame_tool.compositing import composite_frame_pixels

    source = bpy.data.images.new("Roundtrip source", width=2, height=2, alpha=True)
    rgba = np.tile(np.array([0.2, 0.4, 0.8, 1], dtype=np.float32), (2, 2, 1))
    full = SelectionMask(np.ones((2, 2)), (0, 0, 2, 2))
    result = images.create_image_edit_result(source, apply_alpha_mask(rgba, full, "SUBTRACT"), (2, 2))
    result.use_fake_user = True
    name = result.name
    bpy.data.images.remove(source)
    path = str(tmp_path / "mask.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    result = bpy.data.images[name]
    try:
        restored = images.image_rgba(result)
        np.testing.assert_allclose(restored[..., :3], rgba[..., :3], atol=1 / 255)
        np.testing.assert_array_equal(restored[..., 3], 0)
        added = images.create_image_edit_result(result, apply_alpha_mask(restored, full, "EXTEND"), (2, 2))
        bpy.data.images.remove(result)
        result = added
        for _ in range(2):
            source = frame_source_projection(np.eye(4), np.eye(4), np.eye(4), (-1, 1, -1, 1), (2, 2), perspective=False)
            rgba_read = images.image_rgba(result)
            source.update(rgba=rgba_read, pixels=images.premultiplied_rgba(images.image_pixels(result), (2, 2)),
                          image_size=(2, 2), active=True, name=result.name)
            pixels = composite_frame_pixels((source,), ((0, 2), (2, 2), (2, 0), (0, 0)), (2, 2))
            next_result = images.create_image_edit_result(result, pixels, (2, 2))
            bpy.data.images.remove(result)
            result = next_result
            result.reload()
            assert result.alpha_mode == "STRAIGHT" and result.packed_file is not None
            np.testing.assert_allclose(images.image_rgba(result), rgba, atol=1 / 255)
    finally:
        bpy.data.images.remove(result)


def test_job_loader_reads_only_the_returned_file(tmp_path):
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(tmp_path / "foreground.png")
    Image.new("RGBA", (4, 4), (0, 0, 255, 255)).save(tmp_path / "upscale.png")
    original = bpy.data.images.new("Source", width=1, height=1, alpha=True)
    result = images.load_image_edit_result(original, tmp_path / "upscale.png")
    try:
        assert tuple(result.size) == (4, 4)
        assert result.source == "FILE"
        assert result.packed_file is not None
        with pytest.raises(RuntimeError, match="Color result image does not exist"):
            images.load_image_edit_result(original, tmp_path / "missing.png")
    finally:
        bpy.data.images.remove(result)
        bpy.data.images.remove(original)
