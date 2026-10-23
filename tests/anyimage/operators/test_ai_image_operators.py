from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class AiImageOperatorsTest(BlenderTestCase):
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
