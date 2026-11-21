from anyimage.common import projective_image

import unittest
from unittest.mock import patch
from anyimage.operators.frame_tool import compositing, projection as frame_projection


class FrameCompositingTest(unittest.TestCase):
    def test_frame_composites_far_to_near_and_breaks_ties_with_active_on_top(self):
        import numpy as np

        frame = ((0, 2), (2, 2), (2, 0), (0, 0))
        top = self._frame_pixel_source(np.tile((0, 0, 1, .5), (2, 2, 1)), depth=1)
        for depth in (1, 2):
            bottom = self._frame_pixel_source(np.tile((1, 0, 0, 1), (2, 2, 1)), depth=depth, active=False)
            result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
            np.testing.assert_allclose(result.reshape(-1, 4), np.tile((.5, 0, .5, 1), (4, 1)))

    def test_frame_composites_orthographic_samples_at_negative_depth(self):
        import numpy as np

        pixels = np.tile((.25, .5, .75, 1), (2, 2, 1)).astype(np.float32)
        source = self._frame_pixel_source(pixels, depth=-1)
        result = compositing.composite_frame_pixels((source,), ((0, 2), (2, 2), (2, 0), (0, 0)), (2, 2))
        np.testing.assert_array_equal(result.reshape(2, 2, 4), pixels)

    def test_frame_hidden_rgb_uses_bottom_valid_depth_and_stable_ties(self):
        import numpy as np

        blue = np.tile((0, 0, 1, 0), (2, 2, 1))
        red = np.tile((1, 0, 0, 0), (2, 2, 1))
        frame = ((0, 2), (2, 2), (2, 0), (0, 0))
        for depth in (2.0, 1.0, -1.0):
            with self.subTest(depth=depth):
                bottom = self._frame_pixel_source(blue, depth=depth, name="A", active=False)
                top = self._frame_pixel_source(red, depth=min(depth, 1.0))
                result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
                np.testing.assert_allclose(result.reshape((2, 2, 4)), blue)
        middle = self._frame_pixel_source(red, name="B", active=False)
        bottom = self._frame_pixel_source(blue, name="A", active=False)
        top = self._frame_pixel_source(red)
        result = compositing.composite_frame_pixels((middle, top, bottom), frame, (2, 2))
        np.testing.assert_allclose(result.reshape((2, 2, 4)), blue)
        bottom["screen_to_source"][0, 2] += 0.5
        result = np.flipud(compositing.composite_frame_pixels(
            (top, bottom), frame, (2, 2)
        ).reshape((2, 2, 4)))
        np.testing.assert_allclose(result[:, 0], blue[:, 0])
        np.testing.assert_allclose(result[:, 1], red[:, 1])
        bottom["perspective"] = True
        bottom["source_to_view"][2, 2] = 1.0
        result = compositing.composite_frame_pixels((top, bottom), frame, (2, 2))
        np.testing.assert_allclose(result.reshape((2, 2, 4)), red)


    def test_frame_hidden_rgb_tracks_crossing_planes(self):
        import numpy as np

        bottom = self._frame_pixel_source(np.tile((0, 0, 1, 0), (2, 2, 1)), active=False)
        top = self._frame_pixel_source(np.tile((1, 0, 0, 0), (2, 2, 1)))
        bottom["source_to_view"][2] = (2, 0, -2)
        result = np.flipud(compositing.composite_frame_pixels(
            (top, bottom), ((0, 2), (2, 2), (2, 0), (0, 0)), (2, 2)
        ).reshape((2, 2, 4)))
        np.testing.assert_allclose(result[:, 0], np.tile((0, 0, 1, 0), (2, 1)))
        np.testing.assert_allclose(result[:, 1], np.tile((1, 0, 0, 0), (2, 1)))


    def test_frame_blends_rgb_over_bottom_color_with_independent_alpha(self):
        import numpy as np

        for bottom_alpha in (0.0, 0.5, 1.0):
            blue = np.tile((0, 0, 1, bottom_alpha), (2, 5, 1)).astype(np.float32)
            red = np.tile((1, 0, 0, 0), (2, 5, 1)).astype(np.float32)
            red[..., 3] = (0, 0.25, 0.5, 0.75, 1)
            sources = (self._frame_pixel_source(blue, depth=2, active=False),
                       self._frame_pixel_source(red))
            result = np.flipud(compositing.composite_frame_pixels(
                sources, ((0, 2), (5, 2), (5, 0), (0, 0)), (5, 2)
            ).reshape((2, 5, 4)))
            alpha = red[..., 3] + bottom_alpha * (1 - red[..., 3])
            expected = np.zeros_like(red)
            expected[..., 0] = red[..., 3]
            expected[..., 2] = 1 - red[..., 3]
            np.testing.assert_allclose(result[..., 3], alpha)
            np.testing.assert_allclose(result[..., :3], expected[..., :3])


    def test_frame_three_layers_preserve_foreground_gradient_over_white(self):
        import numpy as np

        white = np.tile((1, 1, 1, 0), (2, 6, 1)).astype(np.float32)
        red = np.tile((1, 0, 0, 0), (2, 6, 1)).astype(np.float32)
        red[..., 3] = (0, 0.01, 0.1, 0.25, 0.5, 1)
        blue = np.tile((0, 0, 1, 0.25), (2, 6, 1)).astype(np.float32)
        sources = (
            self._frame_pixel_source(white, depth=3, active=False),
            self._frame_pixel_source(red, depth=2, active=False),
            self._frame_pixel_source(blue),
        )
        result = np.flipud(compositing.composite_frame_pixels(
            sources, ((0, 2), (6, 2), (6, 0), (0, 0)), (6, 2)
        ).reshape((2, 6, 4)))
        red_alpha = red[..., 3:4]
        expected = ((red[..., :3] * red_alpha + 1 - red_alpha) * 0.75
                    + blue[..., :3] * 0.25)
        np.testing.assert_allclose(result[..., :3], expected)
        np.testing.assert_allclose(result[..., 3], 0.25 + red[..., 3] * 0.75)


    def test_frame_foreground_resampling_excludes_hidden_black(self):
        import numpy as np

        white = self._frame_pixel_source(
            np.tile((1, 1, 1, 0), (1, 2, 1)), depth=2, active=False
        )
        foreground = self._frame_pixel_source(
            np.asarray([[(1, 0, 0, 1), (0, 0, 0, 0)]])
        )
        result = compositing.composite_frame_pixels(
            (foreground, white), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(result, (1, 0.5, 0.5, 0.5))


    def test_frame_raw_sampling_and_empty_canvas_are_chunk_independent(self):
        import numpy as np

        rgba = np.tile((0, 1, 0, 0), (4, 4, 1)).astype(np.float32)
        rgba[1:3, 2:] = (1, 0, 0, 1)
        source = self._frame_pixel_source(rgba)
        frame = ((-3, 7), (7, 7), (7, -3), (-3, -3))
        results = []
        for rows in (1, 2, 256):
            with patch.object(compositing, "PROJECTIVE_CHUNK_ROWS", rows):
                results.append(np.flipud(compositing.composite_frame_pixels(
                    (source,), frame, (10, 10)
                ).reshape((10, 10, 4))))
        for result in results:
            np.testing.assert_array_equal(result, results[0])
            np.testing.assert_allclose(result[3:7, 3:7], rgba)
            np.testing.assert_array_equal(result[4, 7], 0)
            np.testing.assert_array_equal(result[0], 0)
        transparent = np.asarray([[(1, 0, 0, 0), (0, 0, 1, 0)]], dtype=np.float32)
        source = self._frame_pixel_source(transparent)
        framed = compositing.composite_frame_pixels(
            (source,), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(framed, (0.5, 0, 0.5, 0))
        sampled = projective_image.sample_rgba(
            transparent, np.asarray(((1, 0.5), (-1, 0.5)))
        )
        np.testing.assert_allclose(sampled, ((0.5, 0, 0.5, 0), (0, 0, 0, 0)))
        transparent[0, 0, 3] = 1
        source = self._frame_pixel_source(transparent)
        framed = compositing.composite_frame_pixels(
            (source,), ((0, 1), (2, 1), (2, 0), (0, 0)), (1, 1)
        )
        np.testing.assert_allclose(framed, (0.5, 0, 0.5, 0.5))


    def _frame_pixel_source(self, rgba, *, depth=1.0, name="Active", active=True):
        import numpy as np

        rgba = np.asarray(rgba, dtype=np.float32)
        height, width = rgba.shape[:2]
        world = np.identity(4)
        world[2, 3] = -depth
        source = frame_projection.frame_source_projection(
            np.identity(4), np.identity(4), world,
            (-1.0, 1.0, -1.0, 1.0), (width, height), perspective=False,
        )
        source.update(
            active=active, name=name, image_size=(width, height), rgba=rgba,
            pixels=projective_image.premultiplied_rgba(
                np.flipud(rgba).ravel(), (width, height)
            ),
        )
        return source
