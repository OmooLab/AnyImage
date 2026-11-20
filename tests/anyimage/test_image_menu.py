from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class ImageMenuTest(BlenderTestCase):
    def test_base_menus_keep_local_actions_and_shared_product_label(self):
        for base_type, full_type, expected in (
            (self.lite_addon.ImageMenuLite, self.anyimage.ImageMenu,
             ["anyimage.convert_to_plane", "anyimage.convert_to_world", "anyimage.set_color_reference", "anyimage.match_color_reference"]),
            (self.lite_addon.ObjectMenuLite, self.anyimage.ObjectMenu,
             ["anyimage.bake_mesh", "anyimage.set_color_reference", "anyimage.match_color_reference"]),
            (self.lite_addon.TextureNodeMenuLite, self.anyimage.TextureNodeMenu,
             ["anyimage.set_color_reference", "anyimage.match_color_reference"]),
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

    def test_image_menu_reflects_target_size_and_available_models(self):
        context = SimpleNamespace(object=SimpleNamespace(
            type="EMPTY", empty_display_type="IMAGE", data=SimpleNamespace(size=(640, 480), get={}.get),
        ))
        for missing, action in (
            (("BEN2_BASE",), "anyimage.download_required_models"),
            ((), "anyimage.open_ai_environment_settings"),
        ):
            with self.subTest(missing=missing):
                layout = Mock()
                status = {"environment_ready": True, "missing_models": missing, "ready": not missing}
                with patch("anyimage.common.ai.ai_status", return_value=status):
                    self.anyimage.ImageMenu.draw(SimpleNamespace(layout=layout), context)
                actions = {call.args[0]: call.kwargs for call in layout.operator.call_args_list}
                self.assertIn(action, actions)
                self.assertEqual(actions["anyimage.upscale_image"]["text"], "Upscale (1280 × 960)")
                self.assertEqual(layout.operator_context, "INVOKE_DEFAULT")

    def test_image_operators_accept_jobs_while_processing(self):
        context = SimpleNamespace(
            object=SimpleNamespace(type="EMPTY", empty_display_type="IMAGE", data={}),
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
