from unittest.mock import patch
import numpy as np


from anyimage.operators.cutout_tool import balloon
from anyimage.operators.cutout_tool.balloon import poisson_balloon_profile


def test_poisson_balloon_profile_is_zero_on_boundary_and_positive_inside():
    points = np.asarray(
        ((0, 0), (2, 0), (2, 2), (0, 2), (1, 1)),
        dtype=float,
    )
    faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))
    boundary = np.asarray((True, True, True, True, False))

    profile = poisson_balloon_profile(points, faces, boundary)

    assert np.all(profile[:4] == 0.0)
    assert profile[4] > 0.0


def test_poisson_balloon_profile_scales_in_world_units():
    points = np.asarray(
        ((0, 0), (2, 0), (2, 2), (0, 2), (1, 1)),
        dtype=float,
    )
    faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))
    boundary = np.asarray((True, True, True, True, False))

    original = poisson_balloon_profile(points, faces, boundary)
    scaled = poisson_balloon_profile(points * 2.0, faces, boundary)

    assert np.isclose(scaled[4], original[4] * 2.0, atol=1e-6)


def test_poisson_balloon_profile_makes_wide_selections_thicker():
    faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))
    boundary = np.asarray((True, True, True, True, False))
    wide = np.asarray(
        ((0, 0), (4, 0), (4, 2), (0, 2), (2, 1)),
        dtype=float,
    )
    narrow = np.asarray(
        ((0, 0), (4, 0), (4, 0.6), (0, 0.6), (2, 0.3)),
        dtype=float,
    )

    wide_profile = poisson_balloon_profile(wide, faces, boundary)
    narrow_profile = poisson_balloon_profile(narrow, faces, boundary)

    assert wide_profile[4] > narrow_profile[4]


def test_teddy_balloon_profile_uses_chordal_axis_radius():
    points = np.asarray(
        ((0, 0), (4, 0), (4, 2), (0, 2), (2, 1)),
        dtype=float,
    )
    faces = ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4))
    boundary = np.asarray((True, True, True, True, False))
    nodes = np.asarray(((1, 1), (3, 1)), dtype=float)

    with patch.object(
        balloon,
        "chordal_axis",
        return_value=(nodes, [(0, 1)], np.asarray((1.0, 1.0))),
    ):
        profile = balloon.teddy_balloon_heights(
            points,
            faces,
            points[:4],
            boundary,
            0.45,
        )

    assert np.all(profile[:4] == 0.0)
    assert np.isclose(profile[4], 0.45, atol=1e-6)
