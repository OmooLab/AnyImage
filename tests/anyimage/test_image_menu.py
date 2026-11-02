from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class ImageMenuTest(BlenderTestCase):
    def test_base_menus_keep_local_actions_and_shared_product_label(self):
        for base_type, full_type, expected in (
            (self.base_addon.ImageMenuBase, self.anyimage.ImageMenu,
             ["anyimage.convert_to_plane", "anyimage.match_color_reference"]),
            (self.base_addon.ObjectMenuBase, self.anyimage.ObjectMenu,
             ["anyimage.bake_mesh", "anyimage.match_color_reference"]),
            (self.base_addon.TextureNodeMenuBase, self.anyimage.TextureNodeMenu,
             ["anyimage.match_color_reference"]),
        ):
            with self.subTest(menu=base_type.__name__):
                calls = []
                layout = SimpleNamespace(
                    operator=lambda identifier, **options: calls.append(identifier),
                    separator=lambda: None,
                )
                base_type.draw(SimpleNamespace(layout=layout), SimpleNamespace())
                self.assertEqual(calls, expected)
                self.assertEqual(layout.operator_context, "INVOKE_DEFAULT")
                self.assertEqual(base_type.bl_label, "Any Image")
                self.assertEqual(full_type.bl_label, "Any Image")
                self.assertEqual(base_type.bl_idname, full_type.bl_idname)

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
                (self.anyimage.ObjectMenu.bl_idname, {}),
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
                ("anyimage.download_required_models", True),
            ],
        )
        self.assertIsNone(labels["anyimage.download_required_models"])

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
        self.assertNotIn(("anyimage.setup_ai_server", True), calls)
        self.assertNotIn(("anyimage.unload_models", True), calls)

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

        menu = self.anyimage.ImageMenu()
        menu.layout = Layout()
        with patch("anyimage.common.ai.ai_status", return_value=status):
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


    def test_image_operators_accept_jobs_while_processing(self):
        context = SimpleNamespace(
            object=SimpleNamespace(type="EMPTY", empty_display_type="IMAGE", data=SimpleNamespace()),
        )
        operators = (
            self.depth_plane_operators.ConvertToDepthPlane,
            self.depth_plane_operators.ConvertToReliefPlane,
            self.remove_background.RemoveImageBackground,
        )

        for busy, expected in ((False, True), (True, True)):
            with (
                self.subTest(busy=busy),
                patch.object(
                    self.anyimage.runtime,
                    "state",
                    return_value="PROCESSING" if busy else "IDLE",
                ),
            ):
                for operator in operators:
                    with self.subTest(operator=operator.__name__):
                        self.assertEqual(operator.poll(context), expected)
