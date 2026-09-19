from types import SimpleNamespace
from tests.support.blender import BlenderTestCase


class RectifyToolTest(BlenderTestCase):
    def test_rectify_rectifies_identity_pixels(self):
        import numpy as np

        top_down = np.arange(3 * 4 * 4, dtype=np.float32).reshape((3, 4, 4))
        top_down /= float(top_down.max())
        top_down[:, :, 3] = 1.0
        result = self.image_data.warp_projective_pixels(
            np.flipud(top_down).ravel(),
            (4, 3),
            ((0, 0), (4, 0), (4, 3), (0, 3)),
            (4, 3),
        )

        np.testing.assert_allclose(
            np.flipud(np.asarray(result).reshape((3, 4, 4))),
            top_down,
            atol=1e-6,
        )


    def test_projective_sampling_keeps_outside_pixels_transparent(self):
        import numpy as np

        source = np.ones((2, 2, 4), dtype=np.float32)
        result = self.image_data.warp_projective_pixels(
            np.flipud(source).ravel(),
            (2, 2),
            ((-2, 0), (2, 0), (2, 2), (-2, 2)),
            (4, 2),
        )
        top_down = np.flipud(np.asarray(result).reshape((2, 4, 4)))

        np.testing.assert_array_equal(top_down[:, :2, 3], 0.0)
        np.testing.assert_allclose(top_down[:, 1, :3], 1.0)
        np.testing.assert_allclose(top_down[:, 2:, 3], 1.0)


    def test_projective_sampling_uses_premultiplied_alpha(self):
        import numpy as np

        source = np.zeros((1, 2, 4), dtype=np.float32)
        source[0, 0] = (1.0, 0.0, 0.0, 1.0)
        source[0, 1] = (0.0, 1.0, 0.0, 0.0)
        sampled = self.image_data.sample_rgba(
            self.image_data.premultiplied_rgba(
                np.flipud(source).ravel(),
                (2, 1),
            ),
            np.asarray([[[1.0, 0.5]]]),
        )
        straight = self.image_data.straight_rgba(sampled)

        np.testing.assert_allclose(straight[0, 0], (1.0, 0.0, 0.0, 0.5))


    def test_homography_rejects_degenerate_points(self):
        with self.assertRaisesRegex(ValueError, "degenerate"):
            self.image_data.homography_from_points(
                ((0, 0), (1, 0), (2, 0), (3, 0)),
                ((0, 0), (1, 0), (1, 1), (0, 1)),
            )


    def test_rectify_preview_uses_srgb_without_changing_pixels(self):
        written = []
        preview = SimpleNamespace(
            colorspace_settings=SimpleNamespace(name="Non-Color"),
            alpha_mode=None,
            pixels=SimpleNamespace(foreach_set=written.extend),
            update=lambda: None,
        )
        previous_data = self.fake_bpy.data
        self.fake_bpy.data = SimpleNamespace(
            images=SimpleNamespace(new=lambda *_args, **_options: preview)
        )
        pixels = (0.1, 0.2, 0.3, 0.4)
        source = SimpleNamespace(
            name="Source.png",
            colorspace_settings=SimpleNamespace(name="Non-Color"),
        )
        try:
            result = self.rectify_preview.create_perspective_preview_image(
                source, pixels
            )
        finally:
            self.fake_bpy.data = previous_data

        self.assertIs(result, preview)
        self.assertEqual(preview.colorspace_settings.name, "sRGB")
        self.assertEqual(preview.alpha_mode, "STRAIGHT")
        self.assertEqual(written, list(pixels))


    def test_rectify_preview_skips_cursor_at_last_clicked_point(self):
        points = ((10.0, 10.0), (80.0, 10.0), (70.0, 60.0))

        stationary = self.rectify_preview.interactive_preview_polygon(
            points, points[-1]
        )
        moving = self.rectify_preview.interactive_preview_polygon(
            points, (20.0, 70.0)
        )

        self.assertEqual(len(stationary), 3)
        self.assertEqual(len(moving), 4)


    def test_rectify_tightly_crops_alpha(self):
        import numpy as np

        top_down = np.zeros((4, 4, 4), dtype=np.float32)
        top_down[1:3, 1:3] = (0.2, 0.4, 0.6, 1.0)
        pixels, output_size, placement_bounds = (
            self.rectify_geometry.extract_perspective_pixels(
                np.flipud(top_down).ravel(),
                (4, 4),
                ((0, 0), (4, 0), (4, 4), (0, 4)),
                1.0,
            )
        )
        result = np.flipud(np.asarray(pixels).reshape((2, 2, 4)))

        self.assertEqual(output_size, (2, 2))
        self.assertEqual(placement_bounds, (1.0, 1.0, 3.0, 3.0))
        self.assertTrue(np.all(result[:, :, 3] == 1.0))


    def test_rectify_rejects_non_convex_corners(self):
        with self.assertRaisesRegex(ValueError, "convex"):
            self.rectify_geometry.validate_perspective_quad(
                ((0, 0), (10, 0), (4, 4), (0, 10))
            )


    def test_rectify_corner_order_is_click_order_independent(self):
        import itertools

        import numpy as np

        corners = ((10, 20), (80, 15), (90, 70), (5, 75))
        ordered = self.rectify_geometry.canonical_perspective_quad(corners)
        for permutation in itertools.permutations(corners):
            np.testing.assert_allclose(
                self.rectify_geometry.canonical_perspective_quad(permutation),
                ordered,
            )


    def test_rectify_detects_source_image_overlap(self):
        overlaps = self.rectify_geometry.perspective_quad_overlaps_image

        self.assertFalse(overlaps(((20, 20), (30, 20), (30, 30), (20, 30)), (10, 10)))
        self.assertTrue(overlaps(((5, 5), (15, 5), (15, 15), (5, 15)), (10, 10)))
        self.assertTrue(overlaps(((-5, -5), (15, -5), (15, 15), (-5, 15)), (10, 10)))


    def test_rectify_limits_output_pixel_count(self):
        width, height = self.image_data.projective_output_size(
            ((0, 0), (10000, 0), (10000, 10000), (0, 10000)),
            1.0,
        )

        self.assertLessEqual(
            width * height,
            self.image_data.MAX_PROJECTIVE_OUTPUT_PIXELS,
        )


    def test_rectify_mouse_adjusts_preview_aspect_exponentially(self):
        adjust = self.rectify_preview.aspect_ratio_from_mouse

        self.assertAlmostEqual(adjust(1.5, 240.0), 3.0)
        self.assertAlmostEqual(adjust(1.5, -240.0), 0.75)
        self.assertEqual(
            adjust(1.0, 100000.0),
            self.rectify_geometry.MAX_INTERACTIVE_ASPECT,
        )
        self.assertEqual(
            self.rectify_preview.snapped_aspect_ratio(1.7),
            (16.0 / 9.0, "16 : 9"),
        )


    def test_rectify_preview_is_centered_at_requested_aspect(self):
        left, bottom, width, height = self.rectify_preview.preview_draw_bounds(
            (1000, 800), 2.0
        )

        self.assertAlmostEqual(width / height, 2.0)
        self.assertAlmostEqual(left + width * 0.5, 500.0)
        self.assertAlmostEqual(bottom + height * 0.5, 400.0)


    def test_rectify_uses_quad_edges_for_initial_aspect(self):
        ratio = self.rectify_geometry.perspective_quad_aspect(
            ((0, 0), (8, 0), (8, 4), (0, 4))
        )

        self.assertAlmostEqual(ratio, 2.0)


    def test_rectify_maps_crop_to_source_plane_bounds(self):
        bounds = self.rectify_geometry.perspective_placement_bounds(
            ((10, 20), (30, 20), (30, 40), (10, 40)),
            (100, 50),
            (-10, -5, 110, 55),
        )

        self.assertEqual(bounds, (8.0, 18.0, 32.0, 42.0))
