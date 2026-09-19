from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class AddonRegistrationTest(BlenderTestCase):
    def test_import_does_not_add_addon_directories_to_sys_path(self):
        self.assertEqual(self.paths_after_import, self.paths_before_import)


    def test_operator_properties_use_plain_names(self):
        operators = self.anyimage.operators
        for operator in operators.CLASSES:
            for name in getattr(operator, "__annotations__", {}):
                self.assertFalse(name.startswith("anyimage_"), (operator, name))


    def test_mesh_operators_are_registered_and_ordered(self):
        from anyimage.operators.convert_to_panorama import ConvertToPanorama, GeneratePanorama

        self.assertIn(ConvertToPanorama, self.anyimage.CLASSES)
        self.assertIn(GeneratePanorama, self.anyimage.CLASSES)
        for generator in (GeneratePanorama, self.convert_to_plane.GenerateDepthPlane):
            self.assertIn(generator, self.anyimage.CLASSES)
            for name in ("source_object_name", "source_identity", "image_identity"):
                self.assertIn(name, generator.__annotations__)
                self.assertIn("HIDDEN", generator.__annotations__[name]["options"])
        self.assertLess(self.anyimage.CLASSES.index(GeneratePanorama), self.anyimage.CLASSES.index(ConvertToPanorama))
        operator = self.convert_to_plane.ConvertToPlane
        self.assertIn(operator, self.anyimage.CLASSES)
        self.assertIn(self.convert_to_plane.ConvertToDepthPlane, self.anyimage.CLASSES)
        self.assertIn(self.convert_to_plane.ConvertToReliefPlane, self.anyimage.CLASSES)
        self.assertIn(self.cutout_main.CutoutSelectionToShape, self.anyimage.CLASSES)
        self.assertEqual(operator.bl_idname, "anyimage.convert_to_plane")
        self.assertIn("REGISTER", operator.bl_options)
        self.assertIn("UNDO", operator.bl_options)

        image_empty = SimpleNamespace(
            type="EMPTY",
            empty_display_type="IMAGE",
            data=object(),
        )
        image_plane = SimpleNamespace(
            type="MESH",
            modifiers=[
                SimpleNamespace(node_group=SimpleNamespace(name="O Image Plane"))
            ],
        )
        plain_mesh = SimpleNamespace(type="MESH", modifiers=[])
        self.assertTrue(operator.poll(SimpleNamespace(object=image_empty)))
        self.assertFalse(operator.poll(SimpleNamespace(object=image_plane)))
        self.assertFalse(operator.poll(SimpleNamespace(object=plain_mesh)))


    def test_image_edit_tools_and_operators_are_registered(self):
        operator = self.edit_mask.EditImageAlpha
        frame_operator = self.image_frame.FrameImages
        self.assertIn(operator, self.anyimage.CLASSES)
        self.assertIn(frame_operator, self.anyimage.CLASSES)
        self.assertIn(
            self.rectify.RectifyImagePerspective,
            self.anyimage.CLASSES,
        )
        mask_tool = self.edit_mask.MaskTool
        self.assertNotIn(mask_tool, self.anyimage.CLASSES)
        self.assertEqual(mask_tool.bl_operator, operator.bl_idname)
        self.assertEqual(operator.bl_options, {"UNDO"})
        frame_tool = self.image_frame.FrameTool
        self.assertNotIn(frame_tool, self.anyimage.CLASSES)
        self.assertEqual(frame_tool.bl_operator, frame_operator.bl_idname)
        self.assertEqual(frame_operator.bl_options, {"UNDO"})
        rectify_tool = self.rectify.RectifyTool
        self.assertNotIn(rectify_tool, self.anyimage.CLASSES)
        self.assertEqual(
            rectify_tool.bl_operator,
            self.rectify.RectifyImagePerspective.bl_idname,
        )

    def test_mask_tool_settings_follow_the_active_gesture(self):
        mask_tool = self.edit_mask.MaskTool
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
            self.anyimage.clipboard_image.PasteClipboardImage,
            self.anyimage.CLASSES,
        )
        self.assertIn(
            self.anyimage.clipboard_image.TrackNativeCopy,
            self.anyimage.CLASSES,
        )
        existing_context_draw = object()
        existing_outliner_draw = object()
        existing_node_draw = object()
        self.context_menu_draws.append(existing_context_draw)
        self.outliner_menu_draws.append(existing_outliner_draw)
        self.node_menu_draws.append(existing_node_draw)

        self.anyimage.register()
        system_classes = self.anyimage.runtime.operator_classes()

        self.assertTrue(set(system_classes) <= set(self.registered))
        self.assertEqual(
            self.registered_tools,
            [
                (
                    self.image_frame.FrameTool,
                    {
                        "group": True,
                        "separator": True,
                    },
                ),
                (
                    self.edit_mask.MaskTool,
                    {
                        "after": {self.image_frame.FrameTool.bl_idname},
                        "separator": False,
                    },
                ),
                (
                    self.rectify.RectifyTool,
                    {
                        "after": {self.edit_mask.MaskTool.bl_idname},
                        "separator": False,
                    },
                ),
                (
                    self.anyimage.CutoutTool,
                    {},
                ),
            ],
        )
        self.assertEqual(len(self.status_bar_draws), 1)
        self.assertEqual(self.status_bar_draws[0]._owner, "anyimage")
        self.assertIs(
            self.context_menu_draws[0],
            self.anyimage.draw_image_context_menu,
        )
        self.assertIs(
            self.outliner_menu_draws[0],
            self.anyimage.draw_image_context_menu,
        )

        self.assertEqual(self.node_menu_draws, [self.anyimage.draw_texture_node_context_menu, existing_node_draw])
        self.assertIn(self.anyimage.AnyImageTextureNodeMenu, self.registered)

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
        self.assertEqual(self.registered_tools, [])
        self.assertEqual(self.status_bar_draws, [])
        self.assertEqual(self.context_menu_draws, [existing_context_draw])
        self.assertEqual(self.outliner_menu_draws, [existing_outliner_draw])
        self.assertEqual(self.node_menu_draws, [existing_node_draw])
        self.anyimage.register()
        self.assertEqual(self.node_menu_draws, [self.anyimage.draw_texture_node_context_menu, existing_node_draw])
        self.anyimage.unregister()
        self.assertEqual(self.node_menu_draws, [existing_node_draw])
