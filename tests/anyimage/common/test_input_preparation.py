from types import SimpleNamespace
from unittest.mock import Mock

import bpy
import pytest
from PIL import Image

from anyimage.common import image_input


def test_packed_image_exports_a_png_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(image_input.tempfile, "tempdir", str(tmp_path))
    image = bpy.data.images.new("Input", width=3, height=2)
    image.pack()
    image.file_format = "JPEG"
    try:
        path = image_input.prepare_image_input(image)
        with Image.open(path) as exported:
            assert exported.format == "PNG" and exported.size == (3, 2)
        assert image.file_format == "JPEG"
        image_input.cleanup_image_input(path)
        assert not list(tmp_path.iterdir())
    finally:
        bpy.data.images.remove(image)


def test_failed_export_restores_format_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setattr(image_input.tempfile, "tempdir", str(tmp_path))
    image = SimpleNamespace(file_format="OPEN_EXR", save=Mock(side_effect=OSError("disk full")))
    with pytest.raises(RuntimeError, match="Unable to export"):
        image_input.save_image_input(image)
    assert image.file_format == "OPEN_EXR"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("source", ["MOVIE", "SEQUENCE"])
def test_animated_inputs_are_rejected_before_export(source):
    with pytest.raises(RuntimeError, match="Only still images"):
        image_input.prepare_image_input(SimpleNamespace(source=source))
