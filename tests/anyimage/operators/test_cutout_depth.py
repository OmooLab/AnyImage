import bpy
import numpy as np
import pytest
from anyimage.operators.cutout_tool.object import load_cutout_node_group
from anyimage.operators.cutout_tool.operators import normal_mode_for_shape
from anyimage.operators.cutout_tool.mesh import build_mesh
from anyimage.operators.cutout_tool.balloon import poisson_balloon_profile


@pytest.mark.parametrize("enabled", [False, True])
def test_depth_presets_always_generate_the_correct_normal_space(enabled):
    assert normal_mode_for_shape("DEPTH_SOLID", enabled) == "OBJECT"
    assert normal_mode_for_shape("DEPTH_SYMMETRY", enabled) == "OBJECT"
    for shape in ("FLAT", "SOLID"):
        assert normal_mode_for_shape(shape, enabled) == ("TANGENT" if enabled else "NONE")


def test_new_cutout_reuses_a_saved_wrapper():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    saved = bpy.data.node_groups.new("O Image Cutout", "GeometryNodeTree")
    saved.interface.new_socket(name="Shape", in_out="INPUT", socket_type="NodeSocketMenu")
    saved.use_fake_user = True
    assert load_cutout_node_group("SOLID") == saved
    assert load_cutout_node_group("FLAT") == saved
    assert saved.name == "O Image Cutout"
    assert any(item.name == "Shape" for item in saved.interface.items_tree)


def test_depth_cutout_reuses_existing_group():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    saved = bpy.data.node_groups.new("O Image Depth Cutout", "GeometryNodeTree")
    assert load_cutout_node_group("DEPTH_SOLID") == saved
    assert saved.name == "O Image Depth Cutout"


def test_small_quality_mesh_has_positive_balloon_support():
    points, faces, boundary, _, _ = build_mesh(np.ones((2, 2)), 32, .9)
    profile = poisson_balloon_profile(points, faces, boundary)
    assert np.all(profile[boundary] == 0)
    assert profile.max() > 0
