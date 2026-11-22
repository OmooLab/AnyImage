from anyimage.common import polygon as polygon_geometry
from anyimage.common.image_gesture import append_lasso_point

from types import SimpleNamespace
from tests.support.blender import BlenderTestCase


def mask_on_canvas(mask, size):
    import numpy as np

    left, top, right, bottom = mask.bounds
    canvas = np.zeros(size[::-1], dtype=np.float32)
    canvas[top:bottom, left:right] = mask.values
    return canvas


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
        )

        self.assertTrue(mask_on_canvas(selection, (12, 9))[3, 5])

        triangles = polygon_geometry.preview_fill_geometry(path)[0]
        preview_area = sum(
            abs(
                polygon_geometry._triangle_cross(
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


    def test_drag_modes_leave_single_click_for_object_selection(self):
        for gesture in ("BRUSH", "LASSO"):
            settings = SimpleNamespace(mask_gesture=gesture, mask_mode="SUBTRACT", mask_radius=25)
            context = SimpleNamespace(scene=SimpleNamespace(anyimage_settings=settings))
            result = self.edit_mask.EditImageAlpha().invoke(context, SimpleNamespace(value="PRESS"))
            self.assertEqual(result, {"PASS_THROUGH"})

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
        triangles = polygon_geometry.triangulated_polygon_vertices(polygon)
        area = sum(
            abs(
                polygon_geometry._triangle_cross(
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


    def test_image_mask_preview_fills_a_self_intersecting_lasso(self):
        polygon = ((0, 0), (4, 4), (0, 4), (4, 0))
        triangles = polygon_geometry.preview_fill_geometry(polygon)[0]
        area = sum(
            abs(
                polygon_geometry._triangle_cross(
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
            polygon_geometry.polygon_self_intersects(
                ((0, 0), (4, 4), (0, 4), (4, 0))
            )
        )
        self.assertFalse(
            polygon_geometry.polygon_self_intersects(
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
        full_mask = mask_on_canvas(mask, (3, 2))
        expected_alpha = {
            "SET": source[:, :, 3] * full_mask,
            "EXTEND": np.maximum(source[:, :, 3], full_mask),
            "SUBTRACT": source[:, :, 3] * (1.0 - full_mask),
        }

        for mode, expected in expected_alpha.items():
            with self.subTest(mode=mode):
                pixels = self.edit_mask.apply_alpha_mask(source.copy(), mask, mode)
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
        single_values = mask_on_canvas(single, (120, 50))
        stroke_values = mask_on_canvas(stroke, (120, 50))

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
        polygons = polygon_geometry.brush_footprint_polygons(
            ((10.0, 10.0), (30.0, 10.0), (15.0, 11.0)),
            5.0,
        )
        bands = polygon_geometry.scanline_union_bands(polygons)
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

        values = mask_on_canvas(selection_mask, (80, 80))
        self.assertGreater(values[40, 40], 0.9)


    def test_image_lasso_does_not_add_stationary_or_nearly_collinear_points(self):
        path = [(0.0, 0.0)]
        samples = list(path)

        self.assertFalse(append_lasso_point(path, (0.0, 0.0), samples))
        self.assertEqual(path, [(0.0, 0.0)])
        self.assertTrue(append_lasso_point(path, (3.0, 0.0), samples))
        self.assertTrue(append_lasso_point(path, (6.0, 0.2), samples))
        self.assertEqual(len(path), 2)
        self.assertEqual(path[-1], (6.0, 0.2))
        self.assertTrue(append_lasso_point(path, (6.0, 4.0), samples))
        self.assertEqual(len(path), 3)
