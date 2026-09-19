import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class MaskToolTest(BlenderTestCase):
    def test_selection_mask_keeps_nonzero_winding_overlap(self):
        path = (
            (1, 1),
            (7, 1),
            (7, 7),
            (1, 7),
            (1, 1),
            (4, 1),
            (10, 1),
            (10, 7),
            (4, 7),
            (4, 1),
            (1, 1),
        )

        selection = self.image_selection.rasterize_selection_path(
            (12, 9),
            self.image_selection.SelectionPath(points=path),
        ).full_values((12, 9))

        self.assertTrue(selection[3, 5])

        triangles = self.image_interaction.preview_fill_geometry(path)[0]
        preview_area = sum(
            abs(
                self.image_interaction._triangle_cross(
                    triangles[index],
                    triangles[index + 1],
                    triangles[index + 2],
                )
            )
            * 0.5
            for index in range(0, len(triangles), 3)
        )

        self.assertAlmostEqual(preview_area, 54.0)


    def test_mask_freezes_scene_settings_on_invoke(self):
        settings = SimpleNamespace(
            mask_gesture="BRUSH",
            mask_mode="EXTEND",
            mask_radius=64,
        )
        context = SimpleNamespace(scene=SimpleNamespace(anyimage_settings=settings))
        operator = SimpleNamespace(gesture="LASSO", mode="SET", radius=25)

        self.edit_mask.EditImageAlpha._read_gesture_settings(operator, context)

        self.assertEqual(operator.gesture, "BRUSH")
        self.assertEqual(operator.mode, "EXTEND")
        self.assertEqual(operator.radius, 64)


    def test_mask_and_rectify_start_after_an_empty_pick(self):
        source = SimpleNamespace(
            name="Source",
            data=SimpleNamespace(size=(8, 6)),
            matrix_world="matrix",
        )
        area = SimpleNamespace(as_pointer=lambda: 1, tag_redraw=Mock())
        region = SimpleNamespace(as_pointer=lambda: 2, width=100, height=80)
        window_manager = SimpleNamespace(
            modal_handler_add=Mock(),
            event_timer_add=Mock(return_value="timer"),
        )
        context = SimpleNamespace(
            area=area,
            region=region,
            window=object(),
            window_manager=window_manager,
            workspace=SimpleNamespace(status_text_set=Mock()),
            scene=SimpleNamespace(
                anyimage_settings=SimpleNamespace(
                    mask_gesture="LASSO",
                    mask_mode="SUBTRACT",
                    mask_radius=25,
                )
            ),
        )
        event = SimpleNamespace(
            mouse_region_x=12,
            mouse_region_y=18,
            value="PRESS",
        )
        previous_space = getattr(self.fake_bpy.types, "SpaceView3D", None)
        self.fake_bpy.types.SpaceView3D = SimpleNamespace(
            draw_handler_add=Mock(return_value="handler")
        )
        try:
            with (
                patch.object(
                    self.image_interaction,
                    "resolve_image_edit_click",
                    return_value=(source, True),
                ),
                patch.object(
                    self.image_interaction,
                    "is_animated_image",
                    return_value=False,
                ),
                patch.object(
                    self.image_interaction,
                    "serialize_matrix",
                    return_value="serialized",
                ),
            ):
                mask = self.edit_mask.EditImageAlpha()
                mask.report = Mock()
                self.assertEqual(mask.invoke(context, event), {"RUNNING_MODAL"})
                self.assertEqual(mask._path, [(12.0, 18.0)])

            with (
                patch.object(
                    self.rectify,
                    "resolve_image_edit_click",
                    return_value=(source, True),
                ),
                patch.object(
                    self.rectify,
                    "is_animated_image",
                    return_value=False,
                ),
                patch.object(
                    self.rectify,
                    "serialize_matrix",
                    return_value="serialized",
                ),
            ):
                rectify = self.rectify.RectifyImagePerspective()
                rectify.report = Mock()
                self.assertEqual(rectify.invoke(context, event), {"RUNNING_MODAL"})
                self.assertEqual(rectify._points, [(12.0, 18.0)])
        finally:
            if previous_space is None:
                del self.fake_bpy.types.SpaceView3D
            else:
                self.fake_bpy.types.SpaceView3D = previous_space


    def test_mask_and_rectify_cancel_without_an_active_image(self):
        context = SimpleNamespace(
            scene=SimpleNamespace(
                anyimage_settings=SimpleNamespace(
                    mask_gesture="LASSO",
                    mask_mode="SUBTRACT",
                    mask_radius=25,
                )
            )
        )
        event = SimpleNamespace()

        with patch.object(
            self.image_interaction,
            "resolve_image_edit_click",
            return_value=(None, False),
        ):
            mask = self.edit_mask.EditImageAlpha()
            mask.report = Mock()
            self.assertEqual(mask.invoke(context, event), {"CANCELLED"})
        with patch.object(
            self.rectify,
            "resolve_image_edit_click",
            return_value=(None, False),
        ):
            rectify = self.rectify.RectifyImagePerspective()
            rectify.report = Mock()
            self.assertEqual(rectify.invoke(context, event), {"CANCELLED"})


    def test_image_mask_fill_triangulates_a_concave_polygon_without_overlap(self):
        polygon = (
            (0, 0),
            (4, 0),
            (4, 4),
            (3, 4),
            (3, 1),
            (1, 1),
            (1, 4),
            (0, 4),
        )
        triangles = self.image_interaction.triangulated_polygon_vertices(polygon)
        area = sum(
            abs(
                self.image_interaction._triangle_cross(
                    triangles[index],
                    triangles[index + 1],
                    triangles[index + 2],
                )
            )
            * 0.5
            for index in range(0, len(triangles), 3)
        )

        self.assertEqual(len(triangles), 18)
        self.assertAlmostEqual(area, 10.0)


    def test_image_mask_fill_uses_blender_geometry_without_stopping_the_draw(self):
        mathutils = ModuleType("mathutils")
        mathutils.Vector = lambda values: values
        mathutils.geometry = SimpleNamespace(
            tessellate_polygon=lambda _loops: (
                ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
            )
        )
        with patch.dict(sys.modules, {"mathutils": mathutils}):
            triangles = self.image_interaction.triangulated_polygon_vertices(
                ((0, 0), (2, 0), (0, 2))
            )

        self.assertEqual(
            triangles,
            ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),
        )


    def test_image_mask_fill_falls_back_when_blender_tessellation_rejects_path(self):
        mathutils = ModuleType("mathutils")
        mathutils.Vector = lambda values: values
        mathutils.geometry = SimpleNamespace(
            tessellate_polygon=lambda _loops: (_ for _ in ()).throw(TypeError())
        )
        with patch.dict(sys.modules, {"mathutils": mathutils}):
            triangles = self.image_interaction.triangulated_polygon_vertices(
                ((0, 0), (2, 0), (0, 2))
            )

        self.assertEqual(len(triangles), 3)


    def test_image_mask_preview_fills_a_self_intersecting_lasso(self):
        polygon = ((0, 0), (4, 4), (0, 4), (4, 0))
        triangles = self.image_interaction.preview_fill_geometry(polygon)[0]
        area = sum(
            abs(
                self.image_interaction._triangle_cross(
                    triangles[index],
                    triangles[index + 1],
                    triangles[index + 2],
                )
            )
            * 0.5
            for index in range(0, len(triangles), 3)
        )

        self.assertTrue(triangles)
        self.assertAlmostEqual(area, 8.0)


    def test_image_mask_preview_detects_only_actual_self_intersections(self):
        self.assertTrue(
            self.image_interaction.polygon_self_intersects(
                ((0, 0), (4, 4), (0, 4), (4, 0))
            )
        )
        self.assertFalse(
            self.image_interaction.polygon_self_intersects(
                ((0, 0), (4, 0), (2, 2), (4, 4), (0, 4))
            )
        )


    def test_mask_alpha_modes_preserve_rgb_and_canvas(self):
        import numpy as np

        source = np.zeros((2, 3, 4), dtype=np.float32)
        source[:, :, :3] = np.asarray((0.2, 0.4, 0.6), dtype=np.float32)
        source[:, :, 3] = np.asarray(((0.2, 0.5, 0.8), (1.0, 0.4, 0.0)))
        mask = self.image_selection.SelectionMask(
            np.asarray(((0.25, 1.0), (0.5, 0.75)), dtype=np.float32),
            (1, 0, 3, 2),
        )
        full_mask = mask.full_values((3, 2))
        expected_alpha = {
            "SET": source[:, :, 3] * full_mask,
            "EXTEND": np.maximum(source[:, :, 3], full_mask),
            "SUBTRACT": source[:, :, 3] * (1.0 - full_mask),
        }

        for mode, expected in expected_alpha.items():
            with self.subTest(mode=mode):
                pixels = self.edit_mask.apply_alpha_mask(source, mask, mode)
                result = np.flipud(pixels.reshape(source.shape))
                np.testing.assert_allclose(result[:, :, :3], source[:, :, :3])
                np.testing.assert_allclose(result[:, :, 3], expected)


    def test_mask_brush_stroke_is_circular_and_continuous(self):
        import numpy as np

        single = self.edit_mask.rasterize_brush_path(
            (120, 50),
            ((20, 25),),
            10,
            lambda path: path,
        )
        stroke = self.edit_mask.rasterize_brush_path(
            (120, 50),
            ((20, 25), (100, 25)),
            10,
            lambda path: path,
        )
        single_values = single.full_values((120, 50))
        stroke_values = stroke.full_values((120, 50))

        self.assertGreater(single_values[25, 20], 0.9)
        self.assertEqual(single_values[0, 0], 0.0)
        self.assertTrue(np.all(stroke_values[25, 20:101] > 0.9))


    def test_mask_brush_clips_bounds_and_projects_screen_radius(self):
        clipped = self.edit_mask.rasterize_brush_path(
            (80, 40),
            ((0, 0),),
            10,
            lambda path: path,
        )
        projected = self.edit_mask.rasterize_brush_path(
            (160, 80),
            ((30, 30),),
            10,
            lambda path: tuple((x * 2.0, y * 0.5) for x, y in path),
        )

        self.assertEqual(clipped.bounds[:2], (0, 0))
        projected_width = projected.bounds[2] - projected.bounds[0]
        projected_height = projected.bounds[3] - projected.bounds[1]
        self.assertGreater(projected_width, projected_height * 3)


    def test_mask_brush_round_turn_stays_inside_the_radius(self):
        polygons = self.image_interaction.brush_footprint_polygons(
            ((10.0, 10.0), (30.0, 10.0), (15.0, 11.0)),
            5.0,
        )
        bands = self.image_interaction.scanline_union_bands(polygons)
        center_band = next(
            band for band in bands if band[0] <= 10.0 < band[1]
        )

        self.assertTrue(
            all(len(intervals) == 1 for _bottom, _top, intervals in bands if intervals)
        )
        self.assertEqual(len(center_band[2]), 1)
        sample_y = (center_band[0] + center_band[1]) / 2
        half_width = (25 - (sample_y - 10) ** 2) ** 0.5
        self.assertAlmostEqual(center_band[2][0][0], 10 - half_width, delta=0.03)
        self.assertAlmostEqual(center_band[2][0][1], 30 + half_width, delta=0.03)


    def test_mask_brush_self_intersection_uses_non_zero_winding(self):
        selection_mask = self.edit_mask.rasterize_brush_path(
            (80, 80),
            ((15, 15), (65, 65), (15, 65), (65, 15)),
            6,
            lambda path: path,
        )

        values = selection_mask.full_values((80, 80))
        self.assertGreater(values[40, 40], 0.9)


    def test_mask_brush_path_builds_one_coverage_after_release(self):
        import numpy as np

        selection_mask = self.edit_mask.rasterize_brush_path(
            (80, 40),
            ((10, 20), (70, 20)),
            6,
            lambda path: path,
        )

        full = selection_mask.full_values((80, 40))
        self.assertTrue(np.all(full[20, 10:71] > 0.9))
        self.assertLess(selection_mask.bounds[0], 10)
        self.assertGreater(selection_mask.bounds[2], 70)


    def test_image_lasso_does_not_add_stationary_or_nearly_collinear_points(self):
        path = [(0.0, 0.0)]
        samples = list(path)

        self.assertFalse(self.image_interaction.append_lasso_point(path, (0.0, 0.0), samples))
        self.assertEqual(path, [(0.0, 0.0)])
        self.assertTrue(self.image_interaction.append_lasso_point(path, (3.0, 0.0), samples))
        self.assertTrue(self.image_interaction.append_lasso_point(path, (6.0, 0.2), samples))
        self.assertEqual(len(path), 2)
        self.assertEqual(path[-1], (6.0, 0.2))
        self.assertTrue(self.image_interaction.append_lasso_point(path, (6.0, 4.0), samples))
        self.assertEqual(len(path), 3)
