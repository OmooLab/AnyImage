from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ImageMenuTest(BlenderTestCase):
    def test_image_menu_keeps_ai_features_clickable_and_offers_models(self):
        calls, labels = self.draw_menu(
            {
                "environment_ready": True,
                "missing_models": ("BEN2_BASE",),
                "ready": False,
            }
        )

        self.assertEqual(
            calls,
            [
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

        calls, _labels = self.draw_menu(
            {"environment_ready": True, "missing_models": (), "ready": True}
        )
        self.assertIn(("anyimage.open_ai_environment_settings", True), calls)
        self.assertNotIn(("anyimage.setup_ai_environment", True), calls)

    def draw_menu(self, status):
        calls = []
        labels = {}

        class Layout:
            operator_context = ""
            enabled = True

            def operator(self, identifier, **options):
                calls.append((identifier, self.enabled))
                labels[identifier] = options.get("text")
                return SimpleNamespace()

            def separator(self):
                calls.append(("separator", self.enabled))

        menu = self.anyimage.AnyImageImageMenu()
        menu.layout = Layout()
        with patch("anyimage.properties.ai_status", return_value=status):
            menu.draw(
                SimpleNamespace(
                    object=SimpleNamespace(
                        type="EMPTY",
                        empty_display_type="IMAGE",
                        data=SimpleNamespace(size=(640, 480)),
                    )
                )
            )
        return calls, labels


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
