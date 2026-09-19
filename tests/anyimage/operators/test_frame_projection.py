import unittest
from types import SimpleNamespace
from anyimage.operators.frame_tool import projection as frame_projection
import numpy as np
import pytest


from anyimage.common.selection import clip_polygon_halfplanes


@pytest.mark.parametrize("focal", [1, 1.7, 2, 4])
@pytest.mark.parametrize("angle,depth", [(30, 0.2), (0, 1e-14)])
def test_frame_overlap_matches_finite_front_samples(focal, angle, depth):
    projection = np.eye(4)
    projection[0, 0] = projection[1, 1] = focal
    projection[3] = (0, 0, -1, 0)
    c, s = np.cos(np.radians(angle)), np.sin(np.radians(angle))
    world = np.eye(4)
    world[:3, :3] = ((c, 0, s), (0, 1, 0), (-s, 0, c))
    world[2, 3] = -depth
    source = frame_projection.frame_source_projection(
        projection, np.eye(4), world, (-1, 1, -1, 1), (100, 100), perspective=True
    )
    source["image_size"] = (100, 100)
    assert frame_projection.frame_source_coordinates(source, np.array(((50, 50),)))[2][0]
    overlap = frame_projection.frame_source_overlap(source, ((0, 100), (100, 100), (100, 0), (0, 0)))
    assert len(overlap) >= 3
    assert np.isfinite(overlap).all()


@pytest.mark.parametrize("scale", [1e-14, 1, 1e14])
def test_halfplane_clipping_is_scale_invariant(scale):
    square = ((0, 0), (2, 0), (2, 2), (0, 2))
    result = clip_polygon_halfplanes(square, ((-scale, 0, scale),))
    assert set(result) == {(0, 0), (1, 0), (1, 2), (0, 2)}
    assert clip_polygon_halfplanes(square, ((1, 0, -3),)) == ()
    edge = clip_polygon_halfplanes(square, ((1, 0, -2),))
    assert all(x == 2 for x, y in edge)


class FrameProjectionTest(unittest.TestCase):
    def test_frame_output_size_uses_viewport_pixels(self):
        frame = (
            (-50.0, 150.0),
            (150.0, 150.0),
            (150.0, -50.0),
            (-50.0, -50.0),
        )

        self.assertEqual(
            frame_projection.frame_output_size(
                frame,
                (1000, 800),
                2048,
            ),
            (200, 200),
        )


    def test_frame_output_size_obeys_region_and_preference_limits(self):
        frame = (
            (0.0, 1000.0),
            (2000.0, 1000.0),
            (2000.0, 0.0),
            (0.0, 0.0),
        )

        self.assertEqual(
            frame_projection.frame_output_size(frame, (1000, 800), 2048),
            (1000, 500),
        )
        self.assertEqual(
            frame_projection.frame_output_size(frame, (4000, 2000), 500),
            (500, 250),
        )


    def test_frame_requires_positive_valid_projection_overlap(self):
        import numpy as np

        source = frame_projection.frame_source_projection(
            np.identity(4),
            np.identity(4),
            np.identity(4),
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=False,
        )

        self.assertTrue(
            frame_projection.frame_source_overlap(
                source,
                ((50.0, 150.0), (150.0, 150.0), (150.0, 50.0), (50.0, 50.0)),
            )
        )
        self.assertFalse(
            frame_projection.frame_source_overlap(
                source,
                ((100.0, 100.0), (200.0, 100.0), (200.0, 0.0), (100.0, 0.0)),
            )
        )


    def test_frame_orthographic_projection_accepts_non_positive_depth(self):
        import numpy as np

        matrix_world = np.identity(4)
        matrix_world[2, 3] = 1.0
        source = frame_projection.frame_source_projection(
            np.identity(4),
            np.identity(4),
            matrix_world,
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=False,
        )
        source["image_size"] = (100, 100)
        points, depth, valid, normalized = frame_projection.frame_source_coordinates(
            source,
            np.asarray(((25.0, 75.0),)),
        )

        np.testing.assert_allclose(points[0], (25.0, 25.0))
        np.testing.assert_allclose(normalized[0], (0.25, 0.25))
        self.assertEqual(depth[0], -1.0)
        self.assertTrue(valid[0])
        self.assertTrue(
            frame_projection.frame_source_overlap(
                source,
                ((0.0, 100.0), (100.0, 100.0), (100.0, 0.0), (0.0, 0.0)),
            )
        )


    def test_frame_rejects_an_orthographic_plane_parallel_to_view_rays(self):
        import numpy as np

        matrix_world = np.asarray(
            (
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (-1.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

        with self.assertRaisesRegex(ValueError, "edge-on"):
            frame_projection.frame_source_projection(
                np.identity(4),
                np.identity(4),
                matrix_world,
                (-1.0, 1.0, -1.0, 1.0),
                (100, 100),
                perspective=False,
            )


    def test_frame_perspective_projection_samples_front_of_crossing_image(self):
        import numpy as np

        projection = np.identity(4)
        projection[3] = (0.0, 0.0, -1.0, 0.0)
        matrix_world = np.identity(4)
        matrix_world[0, 3] = 1.0
        matrix_world[2, 0] = 1.0
        matrix_world[2, 3] = 0.2
        source = frame_projection.frame_source_projection(
            projection,
            np.identity(4),
            matrix_world,
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=True,
        )
        source["image_size"] = (100, 100)
        front_points, front_depth, front_valid, _normalized = (
            frame_projection.frame_source_coordinates(
                source,
                np.asarray(((75.0, 50.0),)),
            )
        )
        _rear_points, rear_depth, rear_valid, _normalized = (
            frame_projection.frame_source_coordinates(
                source,
                np.asarray(((-50.0, 50.0),)),
            )
        )
        overlap = frame_projection.frame_source_overlap(
            source,
            ((50.0, 100.0), (100.0, 100.0), (100.0, 0.0), (50.0, 0.0)),
        )

        self.assertTrue(front_valid[0])
        self.assertGreater(front_depth[0], 0.0)
        self.assertGreaterEqual(front_points[0, 0], 0.0)
        self.assertFalse(rear_valid[0])
        self.assertLess(rear_depth[0], 0.0)
        self.assertTrue(overlap)

        _parallel_points, _parallel_depth, parallel_valid, _normalized = (
            frame_projection.frame_source_coordinates(
                source,
                np.asarray(((0.0, 50.0),)),
            )
        )
        self.assertFalse(parallel_valid[0])


    def test_frame_perspective_projection_accepts_extremely_close_image(self):
        import numpy as np

        projection = np.identity(4)
        projection[3] = (0.0, 0.0, -1.0, 0.0)
        matrix_world = np.identity(4)
        matrix_world[2, 3] = -1e-14
        source = frame_projection.frame_source_projection(
            projection,
            np.identity(4),
            matrix_world,
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=True,
        )
        source["image_size"] = (100, 100)
        _points, depth, valid, _normalized = frame_projection.frame_source_coordinates(
            source,
            np.asarray(((50.0, 50.0),)),
        )

        self.assertTrue(valid[0])
        self.assertEqual(depth[0], 1e-14)


    def test_frame_overlap_does_not_depend_on_output_pixel_centers(self):
        import numpy as np

        source = frame_projection.frame_source_projection(
            np.identity(4),
            np.identity(4),
            np.identity(4),
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=False,
        )

        self.assertTrue(
            frame_projection.frame_source_overlap(
                source,
                (
                    (99.999, 60.0),
                    (100.001, 60.0),
                    (100.001, 40.0),
                    (99.999, 40.0),
                ),
            )
        )


    def test_frame_uses_crossing_active_overlap_for_visible_result_depth(self):
        import numpy as np

        projection = np.identity(4)
        projection[3] = (0.0, 0.0, -1.0, 0.0)
        matrix_world = np.identity(4)
        matrix_world[0, 3] = 1.0
        matrix_world[2, 0] = 1.0
        matrix_world[2, 3] = 0.2
        source = frame_projection.frame_source_projection(
            projection,
            np.identity(4),
            matrix_world,
            (-1.0, 1.0, -1.0, 1.0),
            (100, 100),
            perspective=True,
        )
        source.update(
            {
                "image_size": (100, 100),
                "object": SimpleNamespace(matrix_world=matrix_world),
            }
        )
        frame = ((50.0, 100.0), (100.0, 100.0), (100.0, 0.0), (50.0, 0.0))
        overlap = frame_projection.frame_source_overlap(source, frame)
        depth_location = frame_projection.frame_depth_location(source, overlap)

        self.assertLess(depth_location[2], 0.0)


    def test_frame_keeps_positive_active_origin_as_result_depth_location(self):
        marker = SimpleNamespace(copy=lambda: "active-origin")
        source = {
            "object": SimpleNamespace(
                matrix_world=SimpleNamespace(translation=marker),
            ),
            "origin_depth": 1e-14,
            "perspective": True,
        }

        self.assertEqual(
            frame_projection.frame_depth_location(source, ((0.0, 0.0),)),
            "active-origin",
        )


    def test_frame_geometry_faces_the_view_and_uses_frame_center(self):
        import numpy as np

        matrix, display_size = frame_projection.view_facing_frame_geometry(
            (
                (-2.0, 1.0, 5.0),
                (2.0, 1.0, 5.0),
                (2.0, -1.0, 5.0),
                (-2.0, -1.0, 5.0),
            ),
            (400, 200),
        )

        np.testing.assert_allclose(matrix[:3, 0], (1.0, 0.0, 0.0))
        np.testing.assert_allclose(matrix[:3, 1], (0.0, 1.0, 0.0))
        np.testing.assert_allclose(matrix[:3, 2], (0.0, 0.0, 1.0))
        np.testing.assert_allclose(matrix[:3, 3], (0.0, 0.0, 5.0))
        self.assertEqual(display_size, 4.0)
