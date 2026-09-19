from unittest.mock import patch

import bpy
import pytest

from anyimage.operators import ai_setup, remove_background
from anyimage.operators.convert_to_plane import operators as plane


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
    class RejectInstall(bpy.types.Operator):
        bl_idname = "anyimage.install_environment"
        bl_label = "Reject Install"

        def execute(self, context):
            self.report({"ERROR"}, "Setup unavailable")
            return {"CANCELLED"}

    with patch.object(ai_setup, "ai_status", return_value={"ready": False, "environment_ready": False}):
        bpy.utils.register_class(RejectInstall)
        bpy.utils.register_class(ai_setup.SetupAIEnvironment)
        try:
            with pytest.raises(RuntimeError) as error:
                bpy.ops.anyimage.setup_ai_environment(use_mirror=False)
            assert str(error.value).strip() == "Error: Setup unavailable"
            assert "Traceback" not in capfd.readouterr().err
        finally:
            bpy.utils.unregister_class(ai_setup.SetupAIEnvironment)
            bpy.utils.unregister_class(RejectInstall)
