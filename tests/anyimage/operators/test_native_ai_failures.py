from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bpy
import numpy as np
import pytest
from PIL import Image

from anyimage.operators import ai_setup
from anyimage.operators.convert_to_panorama import operators as panorama
from anyimage.operators.depth_plane import operators as conversion


def test_native_server_controls_are_disabled_during_migration():
    from anyimage.runtime import runtime

    classes = runtime.operator_classes()
    for operator in classes:
        bpy.utils.register_class(operator)
    try:
        with patch.object(runtime, "state", return_value="MIGRATING"):
            for action in ("start_server", "stop_server", "restart_server"):
                assert not getattr(bpy.ops.anyimage, action).poll()
            assert bpy.ops.anyimage.open_server_log.poll()
    finally:
        for operator in reversed(classes):
            bpy.utils.unregister_class(operator)


@pytest.mark.parametrize("module,outer,inner,plane_type", [
    (conversion, conversion.ConvertToDepthPlane, conversion.GeneratePlaneGeometry, "DEPTH"),
    (conversion, conversion.ConvertToReliefPlane, conversion.GeneratePlaneGeometry, "RELIEF"),
    (panorama, panorama.ConvertToPanorama, panorama.GeneratePanorama, None),
])
def test_geometry_job_submits_hdr_as_png_and_cleans_failed_input(module, outer, inner, plane_type, monkeypatch, capfd):
    from anyimage.runtime import runtime

    reason = "Geometry generation failed"
    inputs = []

    def reject(job_type, parameters, **kwargs):
        path = Path(parameters["input"])
        assert list(path.parent.iterdir()) == [path]
        assert parameters["max_input_size"] == 1024
        assert parameters["resolution_level"] == 2
        assert parameters.get("plane_type") == plane_type
        with Image.open(path) as png:
            assert png.format == "PNG" and png.mode == "RGBA"
            assert png.size == ((4, 3) if plane_type else (4, 2))
            assert png.getpixel((0, 0))[3] == 0
            np.testing.assert_allclose(png.getpixel((1, 1)), (231, 231, 231, 128), atol=1)
        inputs.append(path)
        raise RuntimeError(reason)

    monkeypatch.setattr(runtime, "submit", reject)
    monkeypatch.setattr(module, "require_environment", lambda: None)
    monkeypatch.setattr(module, "require_model", lambda model: None)
    monkeypatch.setattr(module, "configured_max_ai_input_size", lambda context: 1024)
    monkeypatch.setattr(module, "addon_preferences", lambda context: SimpleNamespace(geometry_resolution_level=2))
    monkeypatch.setattr(outer, "poll", classmethod(lambda cls, context: True))
    monkeypatch.setattr(module, "invoke_ai_setup_if_needed", lambda _operator: None)
    owner = bpy.data.objects.new("Native validation source", None)
    image = bpy.data.images.new("Native validation image", width=4, height=3, alpha=True, float_buffer=True)
    image.alpha_mode = "PREMUL"
    pixels = np.full((3, 4, 4), 2, dtype=np.float32)
    pixels[..., 3] = 0.5
    pixels[-1, 0] = 0
    image.pixels.foreach_set(pixels.ravel())
    owner.empty_display_type = "IMAGE"
    owner.data = image
    bpy.context.collection.objects.link(owner)
    bpy.context.view_layer.objects.active = owner
    bpy.utils.register_class(inner)
    bpy.utils.register_class(outer)
    try:
        action = getattr(bpy.ops.anyimage, outer.bl_idname.split(".")[1])
        with pytest.raises(RuntimeError) as error:
            action()
        assert str(error.value).strip() == f"Error: {reason}"
        assert "Traceback" not in capfd.readouterr().err
        assert len(inputs) == 1 and not inputs[0].parent.exists()
        assert owner.data == image
    finally:
        bpy.utils.unregister_class(outer)
        bpy.utils.unregister_class(inner)
        bpy.data.objects.remove(owner, do_unlink=True)
        bpy.data.images.remove(image)


def test_native_setup_operator_preserves_plain_error(capfd):
    with (
        patch.object(ai_setup.runtime, "state", return_value="UNAVAILABLE"),
        patch.object(ai_setup.runtime, "setup", side_effect=RuntimeError("Setup unavailable")),
    ):
        classes = (*ai_setup.runtime.operator_classes(), ai_setup.SetupAIServer)
        for cls in classes:
            bpy.utils.register_class(cls)
        try:
            with pytest.raises(RuntimeError) as error:
                bpy.ops.anyimage.setup_ai_server(location="D:/", use_mirror=False)
            assert str(error.value).strip() == "Error: Setup unavailable"
            assert "Traceback" not in capfd.readouterr().err
        finally:
            for cls in reversed(classes):
                bpy.utils.unregister_class(cls)
