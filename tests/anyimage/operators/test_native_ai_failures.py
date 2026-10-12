from unittest.mock import patch

import bpy
import pytest

from anyimage.operators import ai_setup
from anyimage.operators.remove_background import operators as remove_background
from anyimage.operators.convert_to_plane import operators as plane


def test_native_server_controls_are_disabled_during_migration():
    from types import SimpleNamespace
    from blendjob.maintenance import MigrateController
    from anyimage.runtime import runtime

    controller = MigrateController.__new__(MigrateController)
    controller._committed = False
    classes = runtime.operator_classes()
    for operator in classes:
        bpy.utils.register_class(operator)
    try:
        with patch.object(runtime, "active_job", SimpleNamespace(controller=controller)):
            for action in ("start_server", "stop_server", "restart_server", "open_server_log"):
                assert not getattr(bpy.ops.anyimage, action).poll()
            assert bpy.ops.anyimage.cancel_job.poll()
            controller._committed = True
            assert not bpy.ops.anyimage.cancel_job.poll()
    finally:
        for operator in reversed(classes):
            bpy.utils.unregister_class(operator)


@pytest.mark.parametrize("kind", ["background", "depth", "relief"])
def test_nested_native_operator_preserves_plain_error(kind, tmp_path, capfd):
    reason = "Unsupported input format: .tiff"
    if kind == "background":
        inner, outer = remove_background.RunBackgroundRemoval, remove_background.RemoveImageBackground
    else:
        inner = plane.GenerateDepthPlane
        outer = plane.ConvertToDepthPlane if kind == "depth" else plane.ConvertToReliefPlane

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
        patch.object(plane, "invoke_ai_setup_if_needed", return_value=None),
        patch.object(plane, "prepare_material_color_input", return_value=path),
        patch.object(plane, "material_analysis_input", return_value=path),
        patch.object(plane, "depth_plane_settings", return_value=("model", 5)),
        patch.object(plane, "configured_max_ai_input_size", return_value=2048),
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
    with patch.object(ai_setup.runtime, "setup_controller", side_effect=RuntimeError("Setup unavailable")):
        bpy.utils.register_class(ai_setup.SetupAIServer)
        try:
            with pytest.raises(RuntimeError) as error:
                bpy.ops.anyimage.setup_ai_server(location="D:/", use_mirror=False)
            assert str(error.value).strip() == "Error: Setup unavailable"
            assert "Traceback" not in capfd.readouterr().err
        finally:
            bpy.utils.unregister_class(ai_setup.SetupAIServer)
