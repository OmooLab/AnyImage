from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ImageMenuTest(BlenderTestCase):
    def test_cutout_menu_exposes_static_mesh_conversion(self):
        from anyimage import menu

        calls = []
        owner = SimpleNamespace(layout=SimpleNamespace(
            operator=lambda identifier, **options: calls.append(identifier),
            separator=lambda: None,
        ))
        with patch.object(menu.BakeMesh, "poll", return_value=True), patch.object(menu, "draw_image_actions"):
            menu.AnyImageObjectMenu.draw(owner, SimpleNamespace())
        self.assertEqual(calls, [menu.BakeMesh.bl_idname])

    def test_marked_mesh_draws_object_image_menu(self):
        calls = []
        layout = SimpleNamespace(
            menu=lambda identifier, **options: calls.append((identifier, options)),
            separator=lambda: calls.append(("separator", {})),
        )

        class ImageObject(dict):
            type = "MESH"

        marked = ImageObject(o_image_object=True)
        context = SimpleNamespace(object=marked)
        self.anyimage.draw_image_object_context_menu(
            SimpleNamespace(layout=layout),
            context,
        )
        self.assertEqual(
            calls,
            [
                (self.anyimage.AnyImageObjectMenu.bl_idname, {}),
                ("separator", {}),
            ],
        )

        calls.clear()
        self.anyimage.draw_image_object_context_menu(
            SimpleNamespace(layout=layout),
            SimpleNamespace(object=ImageObject()),
        )
        self.assertEqual(calls, [])

    def test_view_3d_image_menu_offers_image_and_ai_actions(self):
        calls, labels, _operators = self.draw_menu(
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
                ("anyimage.match_color_reference", True),
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
        calls, _labels, _operators = self.draw_menu(
            {"environment_ready": True, "missing_models": (), "ready": True}
        )
        self.assertEqual(
            calls[-1:],
            [
                ("anyimage.open_ai_environment_settings", True),
            ],
        )
        self.assertNotIn(("anyimage.setup_ai_environment", True), calls)
        self.assertNotIn(("anyimage.clear_models", True), calls)

    def test_image_menu_uses_invoke_context(self):
        calls, _labels, operators = self.draw_menu(
            {"environment_ready": True, "missing_models": (), "ready": True},
            area_type="OUTLINER",
        )

        self.assertEqual(
            [operator.context for operator in operators],
            ["INVOKE_DEFAULT"] * 8,
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
