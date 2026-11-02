from types import SimpleNamespace
from unittest.mock import patch

import bpy
import pytest

from anyimage.operators import ai_setup
from anyimage.operators.remove_background import operators as remove_background
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


@pytest.mark.parametrize("kind", ["background", "depth", "relief"])
def test_nested_native_operator_preserves_plain_error(kind, tmp_path, capfd):
    reason = "Unsupported input format: .tiff"
    if kind == "background":
        inner, outer = remove_background.RunBackgroundRemoval, remove_background.RemoveImageBackground
    else:
        inner = conversion.GeneratePlaneGeometry
        outer = conversion.ConvertToDepthPlane if kind == "depth" else conversion.ConvertToReliefPlane

    def reject(operator, context):
        operator.report({"ERROR"}, reason)
        return {"CANCELLED"}

    prepared = tmp_path / "prepared"
    prepared.mkdir()
    path = prepared / "input.png"
    path.touch()
    with (
        patch.object(inner, "execute", reject),
        patch.object(outer, "poll", classmethod(lambda cls, context: True)),
        patch.object(conversion, "invoke_ai_setup_if_needed", return_value=None),
        patch.object(conversion, "prepare_material_color_input", return_value=path),
        patch.object(conversion, "material_analysis_input", return_value=path),
        patch.object(conversion, "addon_preferences", return_value=SimpleNamespace(geometry_resolution_level=5)),
        patch.object(conversion, "configured_geometry_model", return_value="model"),
        patch.object(conversion, "configured_max_ai_input_size", return_value=2048),
    ):
        owner = bpy.data.objects.new("Native validation source", None)
        image = bpy.data.images.new("Native validation image", width=1, height=1)
        owner.empty_display_type = "IMAGE"
        owner.data = image
        bpy.context.scene.collection.objects.link(owner)
        bpy.context.view_layer.objects.active = owner
        bpy.utils.register_class(inner)
        bpy.utils.register_class(outer)
        try:
            with pytest.raises(RuntimeError) as error:
                getattr(bpy.ops.anyimage, outer.bl_idname.split(".")[1])()
            assert str(error.value).strip() == f"Error: {reason}"
            assert "Traceback" not in capfd.readouterr().err
            if kind != "background":
                assert not prepared.exists()
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
