from types import SimpleNamespace
from pathlib import Path
import sys
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class AddonRegistrationTest(BlenderTestCase):
    def test_runtime_defaults_preserve_lightweight_backend_boundary(self):
        runtime = self.anyimage.runtime
        entrypoint = Path(self.anyimage.__file__).parent / "server" / "__init__.py"
        self.assertEqual(runtime._config.server_entrypoint, f"{entrypoint.resolve()}:server")
        self.assertIs(runtime.storage_root_setting, self.runtime.storage_root)
        self.assertIs(runtime.post_setup, self.runtime.prepare_models)
        self.assertIn("anyimage.server.model_catalog", sys.modules)
        self.assertNotIn("anyimage.server.model_manager", sys.modules)
        self.assertFalse(any(name.startswith("anyimage.server.jobs.") for name in sys.modules))

    def test_import_does_not_add_addon_directories_to_sys_path(self):
        self.assertEqual(self.paths_after_import, self.paths_before_import)


    def test_image_edit_tools_and_operators_are_registered(self):
        operator = self.edit_mask.EditImageAlpha
        frame_operator = self.image_frame.FrameImages
        self.assertIn(operator, self.anyimage.CLASSES)
        self.assertIn(frame_operator, self.anyimage.CLASSES)
        self.assertIn(
            self.rectify.RectifyImagePerspective,
            self.anyimage.CLASSES,
        )
        mask_tool = self.tools.MaskTool
        self.assertNotIn(mask_tool, self.anyimage.CLASSES)
        self.assertEqual(mask_tool.bl_operator, operator.bl_idname)
        self.assertEqual(operator.bl_options, {"UNDO"})
        frame_tool = self.tools.FrameTool
        self.assertNotIn(frame_tool, self.anyimage.CLASSES)
        self.assertEqual(frame_tool.bl_operator, frame_operator.bl_idname)
        self.assertEqual(frame_operator.bl_options, {"UNDO"})
        rectify_tool = self.tools.RectifyTool
        self.assertNotIn(rectify_tool, self.anyimage.CLASSES)
        self.assertEqual(
            rectify_tool.bl_operator,
            self.rectify.RectifyImagePerspective.bl_idname,
        )

    def test_mask_tool_settings_follow_the_active_gesture(self):
        mask_tool = self.tools.MaskTool
        settings_value = SimpleNamespace(
            mask_gesture="LASSO",
            mask_mode="SET",
            mask_radius=25,
        )
        context = SimpleNamespace(
            scene=SimpleNamespace(anyimage_settings=settings_value)
        )
        drawn_settings = []
        layout = SimpleNamespace(
            prop=lambda _settings, name, **_options: drawn_settings.append(name)
        )
        mask_tool.draw_settings(context, layout, None)
        self.assertEqual(drawn_settings, ["mask_gesture", "mask_mode"])
        settings_value.mask_gesture = "BRUSH"
        drawn_settings.clear()
        mask_tool.draw_settings(context, layout, None)
        self.assertEqual(
            drawn_settings,
            ["mask_gesture", "mask_mode", "mask_radius"],
        )
        settings_value.mask_gesture = "POLYLINE"
        drawn_settings.clear()
        mask_tool.draw_settings(context, layout, None)
        self.assertEqual(drawn_settings, ["mask_gesture", "mask_mode"])


    def test_registration_and_reverse_cleanup_preserve_other_addons(self):
        self.assertIn(
            self.keymaps.PasteClipboardImage,
            self.anyimage.CLASSES,
        )
        existing_context_draw = object()
        existing_outliner_draw = object()
        existing_node_draw = object()
        self.context_menu_draws.append(existing_context_draw)
        self.outliner_menu_draws.append(existing_outliner_draw)
        self.node_menu_draws.append(existing_node_draw)

        self.anyimage.register()
        self.assertIs(
            self.registered_translations[self.anyimage.__package__],
            self.anyimage.TRANSLATIONS,
        )
        cache = self.anyimage.properties
        self.assertIn(cache.restore_color_references, self.fake_bpy.app.handlers.load_post)
        system_classes = self.anyimage.runtime.operator_classes()

        self.assertTrue(set(system_classes) <= set(self.registered))
        self.assertEqual(
            self.registered_tools,
            [
                (
                    self.anyimage.CutoutTool,
                    {
                        "separator": True,
                    },
                ),
                (
                    self.tools.FrameTool,
                    {
                        "after": {self.tools.CutoutTool.bl_idname},
                        "group": True,
                    },
                ),
                (
                    self.tools.MaskTool,
                    {
                        "after": {self.tools.FrameTool.bl_idname},
                        "separator": False,
                    },
                ),
                (
                    self.tools.RectifyTool,
                    {
                        "after": {self.tools.MaskTool.bl_idname},
                        "separator": False,
                    },
                ),
            ],
        )
        self.assertEqual(len(self.status_bar_draws), 1)
        self.assertEqual(
            self.context_menu_draws[:2],
            [
                self.anyimage.draw_image_object_context_menu,
                self.anyimage.draw_image_context_menu,
            ],
        )
        self.assertEqual(self.outliner_menu_draws, [existing_outliner_draw])

        self.assertEqual(self.node_menu_draws, [self.anyimage.draw_texture_node_context_menu, existing_node_draw])
        self.assertIn(self.anyimage.TextureNodeMenu, self.registered)
        self.assertIn(self.anyimage.ObjectMenu, self.registered)
        self.assertIn(self.anyimage.ColorMatchPanel, self.registered)

        unregister_order = []
        original_unregister = self.fake_bpy.utils.unregister_class
        def unregister(cls):
            unregister_order.append(cls)
            original_unregister(cls)
        with patch.object(self.fake_bpy.utils, "unregister_class", side_effect=unregister):
            self.anyimage.unregister()
        self.assertEqual(
            [cls for cls in unregister_order if cls in self.anyimage.CLASSES],
            list(reversed(self.anyimage.CLASSES)),
        )
        self.assertEqual(self.registered, [])
        self.assertEqual(self.registered_translations, {})
        self.assertEqual(self.fake_bpy.app.handlers.load_post, [])
        self.assertEqual(self.fake_bpy.app.handlers.undo_post, [])
        self.assertEqual(self.fake_bpy.app.handlers.redo_post, [])
        self.assertEqual(self.registered_tools, [])
        self.assertEqual(self.status_bar_draws, [])
        self.assertEqual(self.context_menu_draws, [existing_context_draw])
        self.assertEqual(self.outliner_menu_draws, [existing_outliner_draw])
        self.assertEqual(self.node_menu_draws, [existing_node_draw])
        self.anyimage.register()
        self.assertEqual(self.node_menu_draws, [self.anyimage.draw_texture_node_context_menu, existing_node_draw])
        self.anyimage.unregister()
        self.assertEqual(self.node_menu_draws, [existing_node_draw])
