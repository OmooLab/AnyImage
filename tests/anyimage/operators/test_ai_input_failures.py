import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.support.blender import BlenderTestCase


class AiInputFailuresTest(BlenderTestCase):
    def test_image_edits_reject_same_input_before_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.tiff"
            path.touch()
            messages = []
            for module, operator_type in (
                (self.upscale, self.upscale.UpscaleImage),
                (self.remove_background, self.remove_background.RunBackgroundRemoval),
            ):
                operator = operator_type()
                operator.report = Mock()
                target = Mock(image=SimpleNamespace(size=(16, 16)))
                target.prepare.return_value = (path, False)
                context = SimpleNamespace(scene=SimpleNamespace(
                    anyimage_settings=SimpleNamespace()))
                with ExitStack() as stack:
                    stack.enter_context(patch.object(module.ImageEditTarget, "capture", return_value=target))
                    stack.enter_context(patch.object(module, "require_environment"))
                    stack.enter_context(patch.object(module, "require_model"))
                    stack.enter_context(patch.object(self.runtime.runtime, "active_job", None))
                    submit = stack.enter_context(patch.object(self.runtime.runtime, "begin_job"))
                    if module == self.upscale:
                        stack.enter_context(patch.object(module, "configured_upscale_model", return_value="HAT_GAN_X4_SHARPER"))
                        stack.enter_context(patch.object(module, "configured_max_ai_input_size", return_value=2048))
                    self.assertEqual(operator.execute(context), {"CANCELLED"})
                    submit.assert_not_called()
                messages.append(operator.report.call_args.args[1])
                self.assertIsNone(operator._image_target)
                self.assertTrue(path.exists())
            self.assertEqual(messages[0], messages[1])
            self.assertIn("Unsupported input format: .tiff", messages[0])

    def test_invoke_ai_setup_reports_nested_failure(self):
        owner = SimpleNamespace(report=Mock())
        with (
            patch.object(self.ai, "ai_ready", return_value=False),
            patch.object(self.ai.bpy, "ops", SimpleNamespace(anyimage=SimpleNamespace(
                setup_ai_environment=Mock(side_effect=RuntimeError("Error: setup failed\n")))), create=True),
        ):
            self.assertEqual(self.ai.invoke_ai_setup_if_needed(owner), {"CANCELLED"})
        owner.report.assert_called_once_with({"ERROR"}, "setup failed")

    def test_depth_and_relief_cleanup_on_nested_failure(self):
        module = self.convert_to_plane
        for plane_type in ("DEPTH", "RELIEF"):
            for failure in (RuntimeError("Error: invalid input\n"), None):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "prepared" / "input.png"
                    path.parent.mkdir()
                    path.touch()
                    operator = SimpleNamespace(mesh_detail=4, report=Mock())
                    context = SimpleNamespace(object=SimpleNamespace(name="source", as_pointer=lambda: 1,
                        data=SimpleNamespace(as_pointer=lambda: 2)), scene=object())
                    generate = Mock(side_effect=failure, return_value={"CANCELLED"})
                    with (
                        patch.object(module, "invoke_ai_setup_if_needed", return_value=None),
                        patch.object(module, "prepare_material_color_input", return_value=path),
                        patch.object(module, "material_analysis_input", return_value=path),
                        patch.object(module, "depth_plane_settings", return_value=("model", 5)),
                        patch.object(module, "configured_max_ai_input_size", return_value=2048),
                        patch.object(module.bpy, "ops", SimpleNamespace(anyimage=SimpleNamespace(generate_depth_plane=generate)), create=True),
                    ):
                        self.assertEqual(module.start_depth_plane_job(operator, context, plane_type), {"CANCELLED"})
                    self.assertFalse(path.parent.exists())
