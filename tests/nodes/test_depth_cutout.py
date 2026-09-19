"""Behavior checks for the Depth Cutout balloon and shell shapes."""
import bpy
import numpy as np
import pytest

from anyimage.common.object import modifier_input_identifier, set_modifier_input


@pytest.mark.parametrize("mode", [0, 1])
def test_edge_turn_reshapes_thickness_without_moving_zero_thickness(mode):
    """Edge Turn swings the wall direction and leaves zero thickness untouched."""
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface(step=1, resolution=10)
    xz = np.array([(v.co.x, v.co.z) for v in obj.data.vertices])
    profile = .3 * np.sin(np.pi * xz[:, 0] / 2) * np.sin(np.pi * xz[:, 1])
    profile[abs(profile) < 1e-7] = 0
    obj.data.attributes.new("o_balloon", "FLOAT", "POINT").data.foreach_set("value", profile)
    set_value("Mode", mode)
    set_value("Front Inflation", .2)
    modifier = obj.modifiers[0]
    thickness = modifier_input_identifier(modifier.node_group, "Thickness", subtype="DISTANCE" if mode else "NONE")
    turn = modifier_input_identifier(modifier.node_group, "Edge Turn")

    def result(amount, edge_turn):
        set_modifier_input(modifier, thickness, amount)
        set_modifier_input(modifier, turn, edge_turn)
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        return evaluated(obj)

    plain, faces = result(0, 0)
    turned, turned_faces = result(0, 2)
    np.testing.assert_array_equal(plain, turned)
    assert faces == turned_faces
    plain, faces = result(1, 0)
    turned, turned_faces = result(1, 2)
    assert faces == turned_faces
    assert np.isfinite(turned).all()
    assert np.max(np.abs(plain - turned)) > 1e-5


def test_shell_offset_scales_with_thickness_and_ignores_reference():
    """A thin Shell moves a distance proportional to its thickness."""
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface(step=0, resolution=12)
    image = bpy.data.images['Camera']
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(32, 64, 4)
    pixels[..., 2] = 1 + .15 * np.sin(pixels[..., 0] * 6) * np.cos(pixels[..., 1] * 5)
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    set_value('Reference Depth', 10.)
    set_value('Thickness', 0.)
    front, _ = evaluated(obj)

    def offsets(thickness, reference=10.):
        set_value('Thickness', thickness)
        set_value('Reference Depth', reference)
        points, faces = evaluated(obj)
        adjusted_front = front + (0, 10 - reference, 0)
        from scipy.spatial import cKDTree
        distances, indices = cKDTree(adjusted_front).query(points)
        np.testing.assert_allclose(np.sort(distances)[:len(front)], 0, atol=2e-6)
        rear = distances > thickness * .5
        assert rear.sum() == len(front)
        order = np.argsort(indices[rear])
        return ((points[rear] - adjusted_front[indices[rear]]) / thickness)[order], faces

    smooth, faces = offsets(.02)
    thinner, thinner_faces = offsets(.01)
    distant, _ = offsets(.02, 20.)
    np.testing.assert_allclose(thinner, smooth, atol=2e-4)
    np.testing.assert_allclose(distant, smooth, atol=2e-4)
    assert thinner_faces == faces


def test_shell_thickness_extends_behind_the_tilted_front():
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface(step=0, resolution=4)
    image = bpy.data.images["Camera"]
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(32, 64, 4)
    pixels[..., 2] = 1 + 0.4 * pixels[..., 0]
    image.pixels.foreach_set(pixels.ravel())
    image.update()
    obj.update_tag(refresh={"DATA"})
    bpy.context.view_layer.update()
    front, _ = evaluated(obj)
    set_value("Thickness", 0.2)
    set_value("Front Inflation", 0.5)
    points, _ = evaluated(obj)
    front_set = {tuple(point) for point in front}
    assert front_set <= {tuple(point) for point in points}
    assert not np.allclose(points[len(front) :], front, atol=1e-6)


def test_balloon_shell_converges_to_front_with_thickness():
    from scipy.spatial import cKDTree
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface(step=1, resolution=10)
    xz = np.array([(v.co.x, v.co.z) for v in obj.data.vertices])
    profile = 0.3 * np.sin(np.pi * xz[:, 0] / 2) * np.sin(np.pi * xz[:, 1])
    profile[abs(profile) < 1e-7] = 0
    obj.data.attributes.new("o_balloon", "FLOAT", "POINT").data.foreach_set("value", profile)
    set_value("Mode", 0)
    modifier = obj.modifiers[0]
    thickness = modifier_input_identifier(modifier.node_group, "Thickness", subtype="NONE")

    def amount(value):
        set_modifier_input(modifier, thickness, value)
        obj.update_tag(refresh={"DATA"})
        bpy.context.view_layer.update()
        return evaluated(obj)

    front, _ = amount(0)
    tree = cKDTree(front)
    gaps = []
    for value in (0.01, 0.001, 0.0001):
        points, _ = amount(value)
        gaps.append(tree.query(points)[0].max())
    assert gaps[0] > gaps[1] > gaps[2]
    np.testing.assert_allclose(gaps[1] / gaps[0], 0.1, rtol=0.02)


def test_depth_cutout_normal_reduction_uses_point_domain():
    from tests.support.depth_surface import surface

    obj, set_value = surface()
    set_value("Thickness", 0.3)
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        attribute = mesh.attributes["o_normal_reduction"]
        assert attribute.domain == "POINT"
        values = [item.value for item in attribute.data]
        assert 0.0 in values and 1.0 in values
        assert all(np.isfinite(values))
    finally:
        evaluated.to_mesh_clear()


def test_zero_thickness_short_circuits_shell_without_warnings():
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface()
    set_value("Thickness", 0.0)
    points, faces = evaluated(obj)
    assert len(faces) == len(obj.data.polygons)
    modifier = obj.modifiers[0]
    result = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result.to_mesh()
    try:
        assert not list(modifier.node_warnings), [
            warning.message for warning in modifier.node_warnings
        ]
    finally:
        result.to_mesh_clear()


@pytest.mark.parametrize("thickness,inflation", [
    (0.0, 1.0), (0.02, 0.5), (0.1, 1.0),
])
def test_shell_ignores_front_inflation(thickness, inflation):
    from tests.support.depth_surface import surface, evaluated

    obj, set_value = surface(step=0, resolution=10)
    xz = np.array([(v.co.x, v.co.z) for v in obj.data.vertices])
    profile = 0.3 * np.sin(np.pi * xz[:, 0] / 2) * np.sin(np.pi * xz[:, 1])
    profile[abs(profile) < 1e-7] = 0
    obj.data.attributes.new("o_balloon", "FLOAT", "POINT").data.foreach_set("value", profile)
    set_value("Thickness", thickness)
    set_value("Front Inflation", 0.0)
    baseline, baseline_faces = evaluated(obj)
    set_value("Front Inflation", inflation)
    inflated, inflated_faces = evaluated(obj)
    assert baseline_faces == inflated_faces
    np.testing.assert_array_equal(inflated, baseline)
