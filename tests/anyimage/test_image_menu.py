from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ImageMenuTest(BlenderTestCase):
    def test_view_3d_image_menu_offers_tools_and_ai_actions(self):
        calls, labels, operators = self.draw_menu(
            {
                "environment_ready": True,
                "missing_models": ("BEN2_BASE",),
                "ready": False,
            }
        )

        self.assertEqual(
            calls,
            [
                ("anyimage.activate_workspace_tool", True),
                ("separator", True),
                ("anyimage.activate_workspace_tool", True),
                ("anyimage.activate_workspace_tool", True),
                ("anyimage.activate_workspace_tool", True),
                ("separator", True),
                ("anyimage.convert_to_plane", True),
                ("anyimage.convert_to_depth_plane", True),
                ("anyimage.convert_to_relief_plane", True),
                ("anyimage.convert_to_panorama", True),
                ("separator", True),
                ("anyimage.remove_image_background", True),
                ("anyimage.upscale_image", True),
                ("separator", True),
                ("anyimage.setup_ai_environment", True),
            ],
        )
        self.assertEqual(
            labels["anyimage.setup_ai_environment"],
            "Download Required Models…",
        )

        self.assertEqual(
            labels["anyimage.upscale_image"],
            "Upscale (1280 × 960)",
        )
        self.assertEqual(
            [
                (
                    operator.context,
                    operator.text,
                    operator.properties.tool_id,
                )
                for operator in operators
                if operator.identifier == "anyimage.activate_workspace_tool"
            ],
            [
                ("EXEC_DEFAULT", self.tools.CutoutTool.bl_label, self.tools.CutoutTool.bl_idname),
                ("EXEC_DEFAULT", self.tools.FrameTool.bl_label, self.tools.FrameTool.bl_idname),
                ("EXEC_DEFAULT", self.tools.MaskTool.bl_label, self.tools.MaskTool.bl_idname),
                ("EXEC_DEFAULT", self.tools.RectifyTool.bl_label, self.tools.RectifyTool.bl_idname),
            ],
        )

        calls, _labels, _operators = self.draw_menu(
            {"environment_ready": True, "missing_models": (), "ready": True}
        )
        self.assertIn(("anyimage.open_ai_environment_settings", True), calls)
        self.assertNotIn(("anyimage.setup_ai_environment", True), calls)

    def test_outliner_image_menu_does_not_offer_workspace_tools(self):
        calls, _labels, operators = self.draw_menu(
            {"environment_ready": True, "missing_models": (), "ready": True},
            area_type="OUTLINER",
        )

        self.assertNotIn(("anyimage.activate_workspace_tool", True), calls)
        self.assertEqual(
            [operator.context for operator in operators],
            ["INVOKE_DEFAULT"] * 7,
        )

    def draw_menu(self, status, area_type="VIEW_3D"):
        calls = []
        labels = {}
        operators = []

        class Layout:
            operator_context = ""
            enabled = True

            def operator(self, identifier, **options):
                calls.append((identifier, self.enabled))
                labels[identifier] = options.get("text")
                call = SimpleNamespace(
                    identifier=identifier,
                    context=self.operator_context,
                    text=options.get("text"),
                    icon=options.get("icon"),
                    properties=SimpleNamespace(),
                )
                operators.append(call)
                return call.properties

            def separator(self):
                calls.append(("separator", self.enabled))

        menu = self.anyimage.AnyImageImageMenu()
        menu.layout = Layout()
        with patch("anyimage.properties.ai_status", return_value=status):
            menu.draw(
                SimpleNamespace(
                    area=SimpleNamespace(type=area_type),
                    object=SimpleNamespace(
                        type="EMPTY",
                        empty_display_type="IMAGE",
                        data=SimpleNamespace(size=(640, 480)),
                    )
                )
            )
        return calls, labels, operators


    def test_image_operators_stay_clickable_until_server_is_busy(self):
        context = SimpleNamespace(
            object=SimpleNamespace(type="EMPTY", empty_display_type="IMAGE", data=SimpleNamespace()),
        )
        operators = (
            self.convert_to_plane.ConvertToDepthPlane,
            self.convert_to_plane.ConvertToReliefPlane,
            self.remove_background.RemoveImageBackground,
        )

        for busy, expected in ((False, True), (True, False)):
            with (
                self.subTest(busy=busy),
                patch.object(
                    self.anyimage.runtime,
                    "server_busy",
                    return_value=busy,
                ),
            ):
                for operator in operators:
                    with self.subTest(operator=operator.__name__):
                        self.assertEqual(operator.poll(context), expected)
