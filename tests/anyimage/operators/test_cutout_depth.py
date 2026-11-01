import numpy as np
import pytest
from anyimage.operators.cutout_tool.shape import normal_mode_for_shape
from anyimage.operators.cutout_tool.mesh import build_mesh
from anyimage.operators.cutout_tool.balloon import poisson_balloon_profile


@pytest.mark.parametrize("enabled", [False, True])
def test_depth_presets_always_generate_the_correct_normal_space(enabled):
    assert normal_mode_for_shape("DEPTH_SOLID", enabled) == "OBJECT"
    assert normal_mode_for_shape("DEPTH_SYMMETRY", enabled) == "OBJECT"
    for shape in ("FLAT", "SOLID"):
        assert normal_mode_for_shape(shape, enabled) == ("TANGENT" if enabled else "NONE")


def test_small_quality_mesh_has_positive_balloon_support():
    points, faces, boundary, _, _ = build_mesh(np.ones((2, 2)), 32, .9)
    profile = poisson_balloon_profile(points, faces, boundary)
    assert np.all(profile[boundary] == 0)
    assert profile.max() > 0
