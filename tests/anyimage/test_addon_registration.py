from types import SimpleNamespace
from unittest.mock import patch
from tests.support.blender import BlenderTestCase


class AddonRegistrationTest(BlenderTestCase):
    def test_color_reference_property_filters_selector_candidates(self):
        from anyimage.common.image import CLIPBOARD_HASH_PROPERTY

        annotations = self.anyimage.AnyImageSettings.__annotations__
        options = annotations["color_reference"]
        gallery = annotations["color_reference_choice"]
        candidate = SimpleNamespace(
            name="Reference.png",
            size=(4, 3),
            source="FILE",
            get=lambda key, default=None: "clipboard-content" if key == CLIPBOARD_HASH_PROPERTY else default,
        )
        ordinary = SimpleNamespace(
            name="Reference.png",
            size=(4, 3),
            source="FILE",
        )

        self.assertEqual(options["name"], "Reference")
        self.assertTrue(options["poll"](None, candidate))
        self.assertFalse(options["poll"](None, ordinary))
        self.assertEqual(gallery["name"], "Reference")
        self.assertIs(gallery["items"], self.anyimage.properties.color_reference_items)
        self.assertIs(gallery["get"], self.anyimage.properties.get_color_reference_choice)
        self.assertIs(gallery["set"], self.anyimage.properties.set_color_reference_choice)

    def test_color_reference_palette_update_stores_and_clears_dynamic_values(self):
        properties = self.anyimage.properties
        reference = object()
        settings = SimpleNamespace(color_reference=reference)
        colors = ((0.7, 0.1, 0.2), (0.1, 0.4, 0.6), (0.8, 0.7, 0.2))
        weights = (0.5, 0.3, 0.2)

        with patch.object(properties, "get_color_reference", return_value=SimpleNamespace(colors=colors, weights=weights)):
            properties.update_color_reference_palette(settings, None)

        self.assertEqual(settings.color_reference_palette_count, 3)
        self.assertEqual(settings.color_reference_palette_0, colors[0])
        self.assertEqual(settings.color_reference_palette_weight_2, weights[2])
        self.assertEqual(settings.color_reference_palette_3, (0.0, 0.0, 0.0))
        self.assertEqual(settings.color_reference_palette_weight_3, 0.0)

        settings.color_reference = None
        properties.update_color_reference_palette(settings, None)

        self.assertEqual(settings.color_reference_palette_count, 0)
        for name in properties.COLOR_REFERENCE_PALETTE_PROPERTIES:
            self.assertEqual(getattr(settings, name), (0.0, 0.0, 0.0))
        for name in properties.COLOR_REFERENCE_PALETTE_WEIGHT_PROPERTIES:
            self.assertEqual(getattr(settings, name), 0.0)

    def test_job_cleanup_is_registered_without_undo(self):
        from anyimage.operators.job_files import ClearJobFiles

        self.assertIn(ClearJobFiles, self.anyimage.CLASSES)
        self.assertNotIn("UNDO", getattr(ClearJobFiles, "bl_options", set()))

    def test_import_does_not_add_addon_directories_to_sys_path(self):
        self.assertEqual(self.paths_after_import, self.paths_before_import)


    def test_operator_properties_use_plain_names(self):
        operators = self.anyimage.operators
        for operator in operators.CLASSES:
            for name in getattr(operator, "__annotations__", {}):
                self.assertFalse(name.startswith("anyimage_"), (operator, name))


    def test_mesh_operators_are_registered_and_ordered(self):
        from anyimage.operators.convert_to_panorama import ConvertToPanorama, GeneratePanorama
        from anyimage.operators.bake_mesh import BakeMesh

        self.assertIn(BakeMesh, self.anyimage.CLASSES)
        self.assertEqual(BakeMesh.bl_idname, "anyimage.bake_mesh")
        self.assertIn("UNDO", BakeMesh.bl_options)

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
        cache = self.anyimage.properties
        self.assertIn(cache.restore_color_references, self.fake_bpy.app.handlers.load_post)
        system_classes = self.anyimage.runtime.operator_classes()

        self.assertTrue(set(system_classes) <= set(self.registered))
        self.assertEqual(
            self.registered_tools,
            [
                (
                    self.tools.CutoutTool,
                    {
                        "group": True,
                        "separator": True,
                    },
                ),
                (
                    self.tools.FrameTool,
                    {
                        "after": {self.tools.CutoutTool.bl_idname},
                        "separator": False,
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
        self.assertEqual(self.status_bar_draws[0]._owner, "anyimage")
        self.assertEqual(
            self.context_menu_draws[:2],
            [
                self.anyimage.draw_image_object_context_menu,
                self.anyimage.draw_image_context_menu,
            ],
        )
        self.assertEqual(
            self.outliner_menu_draws[:2],
            [
                self.anyimage.draw_image_object_context_menu,
                self.anyimage.draw_image_context_menu,
            ],
        )

        self.assertEqual(self.node_menu_draws, [self.anyimage.draw_texture_node_context_menu, existing_node_draw])
        self.assertIn(self.anyimage.AnyImageTextureNodeMenu, self.registered)
        self.assertIn(self.anyimage.AnyImageObjectMenu, self.registered)
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
