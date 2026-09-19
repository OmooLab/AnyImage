import bpy
import numpy as np

from anyimage.operators.clipboard_image.actions import _set_brush_preview


def test_packed_brush_preview_preserves_image_and_survives_reopen(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Preview Source", width=80, height=40, alpha=True)
    pixels = np.zeros((40, 80, 4), dtype=np.float32)
    pixels[:, :40] = (1.0, 0.0, 0.0, 1.0)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    original_pixels = tuple(image.pixels)
    original_format = image.file_format
    brush = bpy.data.brushes.new("Preview Brush", mode="TEXTURE_PAINT")
    brush.asset_mark()
    try:
        _set_brush_preview(bpy.context, brush, image)
        assert tuple(brush.preview.image_size) == (80, 40)
        preview = np.array(brush.preview.image_pixels_float[:]).reshape(40, 80, 4)
        assert np.allclose(preview[:, :40, 0], 1.0, atol=1 / 255)
        assert np.all(preview[:, :40, 3] == 1.0)
        assert np.all(preview[:, 40:, 3] == 0.0)
        assert tuple(image.pixels) == original_pixels
        assert tuple(image.size) == (80, 40)
        assert image.packed_file is not None
        assert image.file_format == original_format
        expected_preview = tuple(brush.preview.image_pixels)
        path = str(tmp_path / "brush-preview.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        bpy.ops.wm.open_mainfile(filepath=path)
        restored = bpy.data.brushes["Preview Brush"]
        assert tuple(restored.preview.image_size) == (80, 40)
        assert tuple(restored.preview.image_pixels) == expected_preview
    finally:
        bpy.ops.wm.read_factory_settings(use_empty=True)
