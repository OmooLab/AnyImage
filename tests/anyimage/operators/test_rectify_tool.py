from anyimage.common import projective_image

from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase


class RectifyToolTest(BlenderTestCase):
    def test_rectify_preview_uses_shared_linear_pixels_and_cleans_up_on_failure(self):
        import numpy as np

        quad = ((0, 0), (4, 0), (4, 4), (0, 4))
        for floating, fails in ((False, False), (True, False), (True, True)):
            with self.subTest(floating=floating, fails=fails):
                image = SimpleNamespace(is_float=floating, size=(4, 4))
                owner = SimpleNamespace(data=image)
                operator = self.rectify.RectifyImagePerspective()
                operator.source_object_name = "Source"
                operator.source_matrix_data = "matrix"
                operator._points = list(quad[:3])
                operator._phase = "POINTS"
                operator._area_pointer = operator._region_pointer = 0
                operator.report = Mock()
                operator._set_aspect_status = Mock()
                context = SimpleNamespace(
                    region=SimpleNamespace(width=100, height=100), region_data=None,
                    window=SimpleNamespace(cursor_warp=Mock()),
                    workspace=SimpleNamespace(status_text_set=Mock()),
                    area=SimpleNamespace(tag_redraw=Mock()),
                )
                event = SimpleNamespace(type="LEFTMOUSE", value="PRESS", mouse_x=0, mouse_y=4, mouse_region_x=0, mouse_region_y=4)
                source_pixels = np.tile([.5, .5, .5, .25], 16).astype(np.float32)
                preview_pixels = np.tile([.18, .18, .18, .25], 512 * 512).astype(np.float32)
                texture = object()
                with (
                    patch.object(self.rectify, "active_view3d_tool_id", return_value=None),
                    patch.object(self.rectify, "drawing_in_region", return_value=True),
                    patch.object(self.rectify, "require_image_empty", return_value=owner),
                    patch.object(self.rectify, "deserialize_matrix"),
                    patch.object(self.rectify, "image_empty_bounds"),
                    patch.object(self.rectify, "screen_path_to_image_pixels", return_value=quad),
                    patch.object(self.rectify, "image_pixels", return_value=source_pixels),
                    patch.object(self.rectify, "warp_projective_pixels", return_value=preview_pixels) as warp,
                    patch.object(self.rectify, "create_preview_texture", return_value=texture,
                                 side_effect=RuntimeError("GPU failed") if fails else None) as create,
                ):
                    result = operator.modal(context, event)
                expected = .5 if floating else .21404114
                np.testing.assert_allclose(warp.call_args.args[0].reshape((-1, 4))[0], [expected] * 3 + [.25], atol=1e-6)
                np.testing.assert_allclose(create.call_args.args[0][0, 0], [.18, .18, .18, .25])
                if fails:
                    self.assertEqual(result, {"CANCELLED"})
                    self.assertIsNone(operator._preview_texture)
                    self.assertTrue(operator.report.called)
                else:
                    self.assertEqual(result, {"RUNNING_MODAL"})
                    self.assertIs(operator._preview_texture, texture)
                    operator._remove_preview()

    def test_rectify_output_samples_linear_rgb_and_keeps_source_settings(self):
        import numpy as np
        from anyimage.common.color_space import linear_rgb_to_srgb

        for floating in (False, True):
            with self.subTest(floating=floating):
                image = SimpleNamespace(
                    is_float=floating, size=(2, 1), pixels=np.zeros(8),
                    colorspace_settings=SimpleNamespace(name="Custom OCIO"), alpha_mode="PREMUL",
                )
                owner = SimpleNamespace(data=image)
                operator = self.rectify.RectifyImagePerspective()
                operator.source_object_name = "Source"
                operator.quad_json = "[[0,0],[2,0],[2,1],[0,1]]"
                operator.aspect_ratio = 1.0
                operator._source_pixels = np.asarray([0, 0, 0, 1, 1, 1, 1, 1], dtype=np.float32)
                operator.report = Mock()

                def sample_center(pixels, source_size, quad, _aspect):
                    sampled = projective_image.warp_projective_pixels(pixels, source_size, quad, (1, 1))
                    return sampled, (1, 1), (0, 0, 2, 1)

                with (
                    patch.object(self.rectify, "require_image_empty", return_value=owner),
                    patch.object(self.rectify, "is_animated_image", return_value=False),
                    patch.object(self.rectify, "validate_perspective_quad", return_value=((0, 0), (2, 0), (2, 1), (0, 1))),
                    patch.object(self.rectify, "perspective_quad_overlaps_image", return_value=True),
                    patch.object(self.rectify, "extract_perspective_pixels", side_effect=sample_center),
                    patch.object(self.rectify, "create_image_edit_result") as create,
                    patch.object(self.rectify, "replace_empty_image"),
                ):
                    self.assertEqual(operator.execute(SimpleNamespace()), {"FINISHED"})
                expected = .5 if floating else float(linear_rgb_to_srgb(.5))
                np.testing.assert_allclose(create.call_args.args[1], [expected, expected, expected, 1], atol=1e-6)
                self.assertEqual((image.colorspace_settings.name, image.alpha_mode), ("Custom OCIO", "PREMUL"))

    def test_rectify_backspace_releases_preview_and_returns_to_points(self):
        operator = self.rectify.RectifyImagePerspective()
        operator._phase = "ASPECT"
        operator._preview_texture = object()
        operator._source_pixels = object()
        operator._points = [(0, 0), (10, 0), (10, 10), (0, 10)]
        operator._set_point_status = Mock()
        context = SimpleNamespace(area=SimpleNamespace(tag_redraw=Mock()))
        with patch.object(self.rectify, "active_view3d_tool_id", return_value=None):
            result = operator.modal(context, SimpleNamespace(type="BACK_SPACE", value="PRESS"))
        self.assertEqual(result, {"RUNNING_MODAL"})
        self.assertIsNone(operator._preview_texture)
        self.assertIsNone(operator._source_pixels)
        self.assertEqual(operator._phase, "POINTS")
        self.assertEqual(len(operator._points), 3)

    def test_rectify_rectifies_identity_pixels(self):
        import numpy as np

        top_down = np.arange(3 * 4 * 4, dtype=np.float32).reshape((3, 4, 4))
        top_down /= float(top_down.max())
        top_down[:, :, 3] = 1.0
        result = projective_image.warp_projective_pixels(
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
        result = projective_image.warp_projective_pixels(
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
        sampled = projective_image.sample_rgba(
            projective_image.premultiplied_rgba(
                np.flipud(source).ravel(),
                (2, 1),
            ),
            np.asarray([[[1.0, 0.5]]]),
        )
        straight = projective_image.straight_rgba(sampled)

        np.testing.assert_allclose(straight[0, 0], (1.0, 0.0, 0.0, 0.5))


    def test_homography_rejects_degenerate_points(self):
        with self.assertRaisesRegex(ValueError, "degenerate"):
            projective_image.homography_from_points(
                ((0, 0), (1, 0), (2, 0), (3, 0)),
                ((0, 0), (1, 0), (1, 1), (0, 1)),
            )


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
        width, height = projective_image.projective_output_size(
            ((0, 0), (10000, 0), (10000, 10000), (0, 10000)),
            1.0,
        )

        self.assertLessEqual(
            width * height,
            projective_image.MAX_PROJECTIVE_OUTPUT_PIXELS,
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
