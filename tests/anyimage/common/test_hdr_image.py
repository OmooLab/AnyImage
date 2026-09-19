from types import SimpleNamespace
from unittest.mock import patch

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.common.hdr_image import HdrBackgroundInput, recognition_rgba, save_hdr_result
from anyimage.common.image import cleanup_image_input, image_content_state, image_rgba, restore_image_content
from anyimage.common.image_target import ImageEditTarget
from anyimage.common import image_target as targets
from tests.support.image_texture import texture, texture_context
from tests.support.hdr_image import hdr_texture


@pytest.mark.parametrize("source_kind", ["generated", "file", "packed", "dirty"])
@pytest.mark.parametrize("owner_kind", ["texture", "empty"])
@pytest.mark.parametrize("shared", [False, True])
def test_hdr_commit_keeps_float_pixels_and_transaction(hdr_texture, tmp_path, source_kind, owner_kind, shared):
    texture = hdr_texture
    source = texture.image
    rgba = image_rgba(source).copy()
    if source_kind != "generated":
        path = tmp_path / "source.exr"
        save_hdr_result(rgba, path)
        source = bpy.data.images.load(str(path), check_existing=False)
        texture.image = source
        if source_kind == "packed":
            source.pack()
        if source_kind == "dirty":
            rgba[1, 1, 0] = 19
            source.pixels.foreach_set(np.flipud(rgba).ravel())
    source.use_fake_user = True
    if owner_kind == "empty":
        owner = bpy.data.objects.new("HDR Empty", None)
        owner.empty_display_type = "IMAGE"
        owner.data = source
        bpy.context.scene.collection.objects.link(owner)
        texture.image = None
        context = SimpleNamespace(object=owner, space_data=None)
    else:
        owner = texture
        context = texture_context(texture)
    if shared:
        other = texture.id_data.nodes.new("ShaderNodeTexImage")
        other.image = source
    target = ImageEditTarget.capture(context)
    snapshot = HdrBackgroundInput.prepare(source)
    original_state = image_content_state(source)
    alpha = np.linspace(0.03, 0.91, 12, dtype=np.float32).reshape(3, 4)
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, alpha)
    try:
        with Image.open(snapshot.path) as preview:
            assert preview.size == (4, 3)
            assert np.asarray(preview)[0, 0, :3].max() == 0
        result = snapshot.apply(target, alpha_path)
        expected = rgba.copy()
        expected[..., 3] *= alpha
        assert result.is_float and result.packed_file and result.alpha_mode == "CHANNEL_PACKED"
        np.testing.assert_allclose(image_rgba(result), expected, atol=1e-7)
        assert (result == source) == (not shared)
        if shared:
            np.testing.assert_array_equal(image_rgba(other.image), rgba)
        else:
            assert result.use_fake_user
        # The encoded result restores the same ID and floats after a source-state restore.
        result_state = image_content_state(result)
        restore_image_content(result, original_state)
        np.testing.assert_allclose(image_rgba(result), rgba, atol=1e-7)
        restore_image_content(result, result_state)
        np.testing.assert_allclose(image_rgba(result), expected, atol=1e-7)
        blend_path = tmp_path / "roundtrip.blend"
        result_name = result.name
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))
        restored = bpy.data.images[result_name]
        assert restored.is_float and restored.packed_file
        np.testing.assert_allclose(image_rgba(restored), expected, atol=1e-7)
    finally:
        cleanup_image_input(snapshot.path, True)


@pytest.mark.parametrize("invalid", ["shape", "dtype", "nan", "range", "corrupt", "source", "colorspace", "binding"])
def test_hdr_rejects_invalid_result_and_source_changes(hdr_texture, tmp_path, invalid):
    target = ImageEditTarget.capture(texture_context(hdr_texture))
    snapshot = HdrBackgroundInput.prepare(target.image)
    alpha = np.ones((3, 4), np.float32)
    if invalid == "shape": alpha = alpha[:1]
    if invalid == "dtype": alpha = alpha.astype(np.float64)
    if invalid == "nan": alpha[0, 0] = np.nan
    if invalid == "range": alpha[0, 0] = 2
    path = tmp_path / "alpha.npy"
    np.save(path, alpha)
    if invalid == "corrupt": path.write_bytes(b"broken")
    if invalid == "source": target.image.pixels[4] = 20
    if invalid == "colorspace": target.image.colorspace_settings.name = "ACEScg"
    if invalid == "binding": hdr_texture.image = bpy.data.images.new("Other", width=1, height=1)
    before = image_rgba(hdr_texture.image).copy()
    count = len(bpy.data.images)
    try:
        with pytest.raises(RuntimeError):
            snapshot.apply(target, path)
        np.testing.assert_array_equal(image_rgba(hdr_texture.image), before)
        assert len(bpy.data.images) == count
    finally:
        cleanup_image_input(snapshot.path, True)


def test_hdr_preview_is_fixed_and_preserves_source(hdr_texture):
    image = hdr_texture.image
    before = image_rgba(image).copy()
    first = HdrBackgroundInput.prepare(image)
    bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.scene.view_settings.exposure = 7
    second = HdrBackgroundInput.prepare(image)
    try:
        with Image.open(first.path) as a, Image.open(second.path) as b:
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
        np.testing.assert_array_equal(image_rgba(image), before)
        np.testing.assert_array_equal(recognition_rgba(np.zeros((1, 1, 4), np.float32)), [[[0, 0, 0, 1]]])
    finally:
        cleanup_image_input(first.path, True)
        cleanup_image_input(second.path, True)


def test_hdr_rejects_animation_before_export(hdr_texture):
    hdr_texture.image.source = "SEQUENCE"
    with pytest.raises(RuntimeError, match="still images"):
        HdrBackgroundInput.prepare(hdr_texture.image)


def test_hdr_export_failure_releases_blender_resources(hdr_texture, tmp_path):
    images, scenes = len(bpy.data.images), len(bpy.data.scenes)
    blocked = tmp_path / "file"
    blocked.write_bytes(b"not a directory")
    with pytest.raises(RuntimeError):
        save_hdr_result(image_rgba(hdr_texture.image), blocked / "output.exr")
    assert (len(bpy.data.images), len(bpy.data.scenes)) == (images, scenes)


def test_straight_exr_only_changes_alpha(hdr_texture, tmp_path):
    path = tmp_path / "straight.exr"
    encoded = image_rgba(hdr_texture.image).copy()
    save_hdr_result(encoded, path)
    source = bpy.data.images.load(str(path), check_existing=False)
    source.alpha_mode = "STRAIGHT"
    hdr_texture.image = source
    before = image_rgba(source).copy()
    np.testing.assert_allclose(before[..., :3], encoded[..., :3] * encoded[..., 3:4], atol=1e-7)
    snapshot = HdrBackgroundInput.prepare(source)
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, np.full((3, 4), 0.3, np.float32))
    try:
        result = snapshot.apply(ImageEditTarget.capture(texture_context(hdr_texture)), alpha_path)
        rgba = image_rgba(result)
        np.testing.assert_array_equal(rgba[..., :3], before[..., :3])
        np.testing.assert_allclose(rgba[..., 3], before[..., 3] * 0.3, atol=1e-7)
    finally:
        cleanup_image_input(snapshot.path, True)


def test_hdr_failed_commit_restores_unsaved_source(hdr_texture, tmp_path):
    target = ImageEditTarget.capture(texture_context(hdr_texture))
    snapshot = HdrBackgroundInput.prepare(target.image)
    before = image_rgba(target.image).copy()
    original_source = target.image.source
    alpha_path = tmp_path / "alpha.npy"
    np.save(alpha_path, np.full((3, 4), 0.3, np.float32))
    calls = 0

    def fail_first(image, state):
        nonlocal calls
        calls += 1
        restore_image_content(image, state)
        if calls == 1:
            raise RuntimeError("Commit failed")

    count = len(bpy.data.images)
    try:
        with patch.object(targets, "restore_image_content", side_effect=fail_first):
            with pytest.raises(RuntimeError, match="Commit failed"):
                snapshot.apply(target, alpha_path, prepare_undo=True)
        np.testing.assert_array_equal(image_rgba(target.image), before)
        assert target.image.source == original_source
        assert len(bpy.data.images) == count
    finally:
        cleanup_image_input(snapshot.path, True)
