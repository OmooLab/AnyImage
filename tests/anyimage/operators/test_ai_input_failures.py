import tempfile
from unittest.mock import Mock

import bpy
import pytest
from PIL import Image

from anyimage.operators import upscale
from anyimage.operators.remove_background import operators as background
from anyimage.runtime import runtime


@pytest.mark.parametrize("module", [upscale, background], ids=["upscale", "remove_background"])
def test_unsupported_file_is_reported_before_submission(module, tmp_path, monkeypatch, capfd):
    source = tmp_path / "original.tiff"
    Image.new("RGB", (16, 16), (32, 64, 128)).save(source)
    original = source.read_bytes()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    image = bpy.data.images.load(str(source), check_existing=False)
    owner = bpy.data.objects.new("Image to edit", None)
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.collection.objects.link(owner)
    bpy.context.view_layer.objects.active = owner
    monkeypatch.setattr(runtime, "can_submit", lambda: True)
    monkeypatch.setattr(module, "require_environment", lambda: None)
    monkeypatch.setattr(module, "require_model", lambda _model: None)
    submit = Mock()
    monkeypatch.setattr(runtime.server, "submit", submit)
    classes = ((upscale.UpscaleImage,) if module is upscale else
               (background.RunBackgroundRemoval, background.RemoveImageBackground))
    for cls in classes:
        bpy.utils.register_class(cls)
    try:
        action = getattr(bpy.ops.anyimage, classes[-1].bl_idname.split(".")[1])
        with pytest.raises(RuntimeError) as error:
            action()
        assert str(error.value).startswith("Error: Unsupported input format: .tiff")
        assert "Traceback" not in capfd.readouterr().err
        submit.assert_not_called()
        assert list(tmp_path.iterdir()) == [source] and source.read_bytes() == original
    finally:
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)
