import bpy
import numpy as np
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from anyimage.operators.clipboard_image.brush import set_brush_preview
from anyimage.operators.clipboard_image.actions import (
    ClipboardImageTarget, replace_pasted_image,
)


def test_failed_preview_export_restores_format_and_removes_directory():
    image = SimpleNamespace(file_format="OPEN_EXR", save=Mock(side_effect=OSError("disk full")))
    with pytest.raises(RuntimeError, match="disk full"):
        set_brush_preview(bpy.context, None, image)
    assert image.file_format == "OPEN_EXR"
    assert not Path(image.save.call_args.kwargs["filepath"]).parent.exists()


def test_packed_brush_replacement_updates_preview_and_survives_reopen(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Preview Source", width=80, height=40, alpha=True)
    pixels = np.zeros((40, 80, 4), dtype=np.float32)
    pixels[:, :40] = (1.0, 0.0, 0.0, 1.0)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    image.file_format = "JPEG"
    original_pixels = tuple(image.pixels)
    original_format = image.file_format
    brush = bpy.data.brushes.new("Preview Brush", mode="TEXTURE_PAINT")
    brush.asset_mark()
    texture = bpy.data.textures.new("Preview Texture", type="IMAGE")
    texture.image = image
    brush.texture = texture
    try:
        set_brush_preview(bpy.context, brush, image)
        assert tuple(brush.preview.image_size) == (80, 40)
        preview = np.array(brush.preview.image_pixels_float[:]).reshape(40, 80, 4)
        assert np.allclose(preview[:, :40, 0], 1.0, atol=1 / 255)
        assert np.all(preview[:, :40, 3] == 1.0)
        assert np.all(preview[:, 40:, 3] == 0.0)
        assert tuple(image.pixels) == original_pixels
        assert tuple(image.size) == (80, 40)
        assert image.packed_file is not None
        assert image.file_format == original_format
        replacement = bpy.data.images.new("Incoming", width=40, height=80, alpha=True)
        replacement.pixels[:] = [0, 1, 0, 1] * (40 * 80)
        replacement.pack()
        context = SimpleNamespace(
            mode="PAINT_TEXTURE", scene=bpy.context.scene,
            temp_override=bpy.context.temp_override,
        )
        pasted = replace_pasted_image(ClipboardImageTarget(image, texture, brush), replacement)
        set_brush_preview(context, brush, pasted)
        bpy.data.images.remove(replacement)
        assert brush.texture == texture and texture.image == image
        assert image.name == "Preview Source" and tuple(image.size) == (40, 80)
        assert tuple(brush.preview.image_size) == (40, 80)
        preview = np.array(brush.preview.image_pixels_float[:]).reshape(80, 40, 4)
        np.testing.assert_allclose(preview, np.tile([0, 1, 0, 1], (80, 40, 1)), atol=1 / 255)
        expected_preview = tuple(brush.preview.image_pixels)
        path = str(tmp_path / "brush-preview.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        restored = bpy.data.brushes["Preview Brush"]
        assert tuple(restored.preview.image_size) == (40, 80)
        assert tuple(restored.preview.image_pixels) == expected_preview
        assert restored.texture.name == "Preview Texture"
        assert restored.texture.image.name == "Preview Source"
        assert tuple(restored.texture.image.size) == (40, 80)
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)
