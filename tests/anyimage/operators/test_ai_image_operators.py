from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class AiImageOperatorsTest(BlenderTestCase):
    def test_upscale_operator_sends_the_selected_model(self):
        operator_type = self.upscale.UpscaleImage
        self.assertIn(operator_type, self.anyimage.CLASSES)
        self.assertIn(self.runtime.JobOperatorBase, operator_type.__mro__)
        self.assertEqual(operator_type.bl_options, {"UNDO"})
        operator = operator_type()
        operator.input_path = "input.png"
        operator._image_target = SimpleNamespace()
        operator.model = "HAT_GAN_X4_SHARPER"
        operator.max_input_size = 1024
        context = SimpleNamespace(
            scene=SimpleNamespace(anyimage_settings=SimpleNamespace())
        )
        with (
            patch.object(self.upscale, "require_environment"),
            patch.object(self.upscale, "require_model") as require_model,
            patch.object(
                self.upscale, "require_input_path", return_value=Path("input.png")
            ),
            patch.object(self.upscale, "production_device", return_value="CUDA"),
        ):
            request = operator.request(context)

        require_model.assert_called_once_with("HAT_GAN_X4_SHARPER")
        self.assertEqual(
            request,
            {
                "input": "input.png",
                "model": "HAT_GAN_X4_SHARPER",
                "device": "cuda",
                "max_input_size": 1024,
            },
        )


    def test_upscale_operator_opens_setup_when_required_ai_is_missing(self):
        expected = {"CANCELLED"}
        operator = self.upscale.UpscaleImage()
        with patch.object(
            self.upscale,
            "invoke_ai_setup_if_needed",
            return_value=expected,
        ) as setup:
            result = operator.invoke(None, None)

        setup.assert_called_once_with(operator)
        self.assertIs(result, expected)


    def test_upscale_operator_runs_immediately_when_ai_is_ready(self):
        operator = self.upscale.UpscaleImage()
        context = object()
        expected = {"FINISHED"}
        with (
            patch.object(
                self.upscale,
                "invoke_ai_setup_if_needed",
                return_value=None,
            ),
            patch.object(
                operator,
                "execute",
                return_value=expected,
            ) as execute,
        ):
            result = operator.invoke(context, None)

        execute.assert_called_once_with(context)
        self.assertIs(result, expected)
        self.assertNotIn("REGISTER", operator.bl_options)


    def test_remove_background_loads_a_plain_image_edit_result(self):
        result = SimpleNamespace(file=lambda key: Path("result") / f"{key}.png")
        operator = self.remove_background.RunBackgroundRemoval()
        operator._image_target = Mock()
        ops = SimpleNamespace(
            ed=SimpleNamespace(undo_push=Mock(return_value={"FINISHED"}))
        )
        with (
            patch.object(self.remove_background.bpy, "ops", ops, create=True),
        ):
            operator.response(None, result)

        operator._image_target.apply.assert_called_once_with(Path("result/foreground.png"))
        ops.ed.undo_push.assert_called_once_with(message="Remove Background")


    def test_upscale_loads_a_plain_image_edit_result(self):
        result = SimpleNamespace(file=lambda key: Path("result") / f"{key}.png")
        operator = self.upscale.UpscaleImage()
        operator._image_target = Mock()
        operator.model = "HAT_GAN_X4_SHARPER"
        with (
            patch.object(
                self.upscale,
                "upscale_model_label",
                return_value="HAT Sharper",
            ),
        ):
            message = operator.response(None, result)

        operator._image_target.apply.assert_called_once_with(
            Path("result/upscale.png"),
        )
        self.assertEqual(message, "Image is upscaled with HAT Sharper")
