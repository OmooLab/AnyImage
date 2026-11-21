from anyimage.common import projective_image

from types import SimpleNamespace
from unittest.mock import Mock, patch
from tests.support.blender import BlenderTestCase
import bpy
import numpy as np
import pytest


@pytest.mark.parametrize("change", ["rename", "binding", "pixels", "colorspace", "alpha_mode"])
def test_rectify_preview_keeps_its_source_and_rejects_external_changes(change):
    from anyimage.common.color_space import image_rgba_to_linear
    from anyimage.common.image import image_content_signature, image_pixels
    from anyimage.operators.rectify_tool import operators

    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Rectify source", width=2, height=2, alpha=True)
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(np.tile(np.array([0.2, 0.5, 0.8, 1.0], np.float32), 4))
    source = bpy.data.objects.new("Rectify Empty", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    bpy.context.collection.objects.link(source)
    pixels = image_pixels(image)
    operator = SimpleNamespace(
        _source_object=source, _source_image=image,
        _source_linear=image_rgba_to_linear(image, pixels.reshape(-1, 4)).ravel(),
        _source_signature=image_content_signature(image, pixels),
        source_object_name=source.name, quad_json="[[0,0],[2,0],[2,2],[0,2]]",
        aspect_ratio=1.0, report=Mock(),
    )
    if change == "rename":
        source.name = "Renamed during preview"
    elif change == "binding":
        source.data = bpy.data.images.new("Replacement", width=2, height=2, alpha=True)
    elif change == "pixels":
        image.pixels[0] = 0.9
        image.update()
    elif change == "colorspace":
        image.colorspace_settings.name = "Non-Color"
    else:
        image.alpha_mode = "CHANNEL_PACKED"
    current = source.data
    before = image_pixels(current)
    result = operators.RectifyImagePerspective.execute(operator, SimpleNamespace())
    if change == "rename":
        assert result == {"FINISHED"}
        assert operator.source_object_name == "Renamed during preview"
        np.testing.assert_array_equal(image_pixels(source.data), before)
    else:
        assert result == {"CANCELLED"}
        assert source.data == current
        np.testing.assert_array_equal(image_pixels(current), before)
    bpy.ops.wm.read_factory_settings(use_empty=True)


@pytest.mark.parametrize("floating", [False, True])
def test_rectify_preview_and_confirm_use_the_same_linear_image(monkeypatch, floating):
    from anyimage.common.color_space import linear_rgb_to_srgb, srgb_to_linear_rgb
    from anyimage.common.image import image_content_signature, image_pixels
    from anyimage.operators.rectify_tool import operators

    bpy.ops.wm.read_factory_settings(use_empty=True)
    image = bpy.data.images.new("Rectify", width=5, height=4, alpha=True, float_buffer=floating)
    rgba = np.ones((4, 5, 4), dtype=np.float32)
    rgba[:, ::2, :3] = .25
    image.pixels.foreach_set(rgba.ravel())
    source = bpy.data.objects.new("Rectify", None)
    source.empty_display_type = "IMAGE"
    source.data = image
    bpy.context.collection.objects.link(source)
    original = image_pixels(image)
    quad = ((0, 0), (4, 0), (4, 4), (0, 4))
    image_quad = np.asarray(quad) + (.5, 0)
    class PreviewOperator(SimpleNamespace):
        _begin_aspect_preview = operators.RectifyImagePerspective._begin_aspect_preview

    operator = PreviewOperator(
        _source_object=source, _source_image=image, _source_signature=image_content_signature(image),
        _source_matrix=source.matrix_world.copy(), _points=list(quad[:3]), _phase="POINTS",
        _area_pointer=0, _region_pointer=0, _set_aspect_status=Mock(), _finish=Mock(),
        report=Mock(),
    )
    context = SimpleNamespace(region=SimpleNamespace(width=100, height=100), region_data=None,
                              window=Mock(), area=Mock())
    event = SimpleNamespace(type="LEFTMOUSE", value="PRESS", mouse_x=0, mouse_y=4, mouse_region_x=0, mouse_region_y=4)
    monkeypatch.setattr(operators, "drawing_in_region", lambda *_: True)
    monkeypatch.setattr(operators, "screen_path_to_image_pixels", lambda *_: image_quad)
    monkeypatch.setattr(operators, "create_preview_texture", lambda pixels: pixels)
    assert operators.RectifyImagePerspective.modal(operator, context, event) == {"RUNNING_MODAL"}
    dark = original[0] if floating else srgb_to_linear_rgb(original[0])
    np.testing.assert_allclose(operator._preview_texture[256, 0, :3], dark + (1 - dark) / 256, atol=1e-6)
    assert operators.RectifyImagePerspective.execute(operator, context) == {"FINISHED"}
    average = (1 + dark) * .5
    expected = average if floating else linear_rgb_to_srgb(average)
    np.testing.assert_allclose(image_pixels(source.data).reshape(-1, 4)[:, :3], expected, atol=1/255)
    bpy.ops.wm.read_factory_settings(use_empty=True)


class RectifyToolTest(BlenderTestCase):
    def test_concave_screen_selection_is_rejected_before_reading_pixels(self):
        operator = self.rectify.RectifyImagePerspective()
        operator._points = [(0, 0), (20, 0), (4, 4), (0, 20)]
        with patch.object(self.rectify, "read_conversion_source") as read:
            with self.assertRaisesRegex(ValueError, "convex"):
                operator._begin_aspect_preview(None, None)
        read.assert_not_called()

    def test_right_click_removes_corners_then_cancels_at_first_point(self):
        operator = self.rectify.RectifyImagePerspective()
        operator._phase = "POINTS"
        operator._points = [(0, 0), (10, 0)]
        operator._set_point_status = Mock()
        operator._finish = Mock()
        context = SimpleNamespace(area=Mock())
        event = SimpleNamespace(type="RIGHTMOUSE", value="PRESS")
        with patch.object(self.rectify, "active_view3d_tool_id", return_value=None):
            self.assertEqual(operator.modal(context, event), {"RUNNING_MODAL"})
            self.assertEqual(operator._points, [(0, 0)])
            self.assertEqual(operator.modal(context, event), {"CANCELLED"})
        operator._finish.assert_called_once_with(context)

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
