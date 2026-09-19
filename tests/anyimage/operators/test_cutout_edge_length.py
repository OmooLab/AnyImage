from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy
import numpy as np
import pytest
from mathutils import Matrix

from anyimage import properties
from anyimage.operators.cutout_tool import geometry as g
from anyimage.operators.cutout_tool import operators


def source_plane(size=(100, 100), display_size=1, matrix=None):
    return SimpleNamespace(
        data=SimpleNamespace(size=size),
        empty_display_size=display_size,
        empty_image_offset=(-0.5, -0.5),
        matrix_world=Matrix.Identity(4) if matrix is None else matrix,
    )


def test_relative_floor_uses_visible_world_bounds(monkeypatch):
    monkeypatch.setattr(g, "configured_min_cutout_relative_edge_length", lambda _: 0.01)
    alpha = np.zeros((100, 100))
    alpha[25:75, 25:75] = 1
    source = source_plane(display_size=2)
    resolve = lambda length: g.effective_cutout_edge_length(None, source, length, alpha, (0, 0, 100, 100))
    assert resolve(0.001) == 0.01
    assert resolve(0.1) == 0.1
    source.matrix_world = Matrix.Rotation(0.7, 4, "Y") @ Matrix.Diagonal((2, 3, 1, 1))
    assert resolve(0.001) == pytest.approx(0.03)
    monkeypatch.setattr(g, "configured_min_cutout_relative_edge_length", lambda _: 0.02)
    assert resolve(0.001) == pytest.approx(0.06)


@pytest.mark.parametrize("fine_outline", (False, True))
def test_mesh_density_survives_resolution_and_canvas_changes(fine_outline):
    meshes = []
    for size, display_size, inset in ((100, 1, 0), (200, 1, 0), (200, 2, 50)):
        source = source_plane((size, size), display_size)
        alpha = np.zeros((size, size))
        alpha[inset:size-inset, inset:size-inset] = 1
        spacing = g.effective_cutout_edge_length(bpy.context, source, 0.1, alpha, (0, 0, size, size))
        assert spacing == 0.1
        meshes.append(g.build_base_shape(bpy.context, source, spacing, alpha, (0, 0, size, size), fine_outline=fine_outline))
    counts = [len(mesh.vertices) for mesh in meshes]
    assert max(counts) / min(counts) < 1.05
    for mesh in meshes:
        assert np.isfinite(mesh.vertices).all()
        np.testing.assert_allclose(np.ptp(mesh.vertices[:, [0, 2]], axis=0), (1, 1), atol=0.03)


@pytest.mark.parametrize("fine_outline", (False, True))
def test_world_scaling_adds_samples_and_rotation_preserves_density(fine_outline):
    alpha = np.ones((100, 100))
    counts = []
    for matrix in (Matrix.Identity(4), Matrix.Diagonal((2, 3, 1, 1)),
                   Matrix.Rotation(0.6, 4, "Z") @ Matrix.Diagonal((2, 3, 1, 1))):
        source = source_plane(matrix=matrix)
        mesh = g.build_base_shape(bpy.context, source, 0.1, alpha, (0, 0, 100, 100), fine_outline=fine_outline)
        counts.append(len(mesh.vertices))
        planar = mesh.vertices[:, [0, 2]] @ g.metric_transform(g.world_plane_metric(matrix)[0])
        edges = np.unique(np.sort(np.concatenate([mesh.faces[:, [0, 1]], mesh.faces[:, [1, 2]], mesh.faces[:, [2, 0]]]), axis=1), axis=0)
        lengths = np.linalg.norm(planar[edges[:, 0]] - planar[edges[:, 1]], axis=1)
        assert 0.06 < np.median(lengths) < 0.14
    assert counts[1] > counts[0] * 4
    assert abs(counts[2] - counts[1]) < counts[1] * 0.02


def test_length_property_uses_scene_units_and_preserves_physical_value():
    class CutoutLengthTestSettings(bpy.types.PropertyGroup):
        edge_length: properties.cutout_edge_length_property(store_meters=True)

    scene = bpy.context.scene
    previous_scale, previous_system = scene.unit_settings.scale_length, scene.unit_settings.system
    bpy.utils.register_class(CutoutLengthTestSettings)
    bpy.types.Scene.cutout_length_test = bpy.props.PointerProperty(type=CutoutLengthTestSettings)
    try:
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 0.01
        settings = scene.cutout_length_test
        assert settings.edge_length == pytest.approx(10)
        settings.edge_length = bpy.utils.units.to_value("METRIC", "LENGTH", "0.2m") / scene.unit_settings.scale_length
        assert settings.edge_length == pytest.approx(20)
        scene.unit_settings.scale_length = 1
        assert settings.edge_length == pytest.approx(0.2)
    finally:
        scene.unit_settings.scale_length = previous_scale
        scene.unit_settings.system = previous_system
        if "cutout_length_test" in scene:
            del scene["cutout_length_test"]
        del bpy.types.Scene.cutout_length_test
        bpy.utils.unregister_class(CutoutLengthTestSettings)


def test_operator_length_property_accepts_world_units():
    captured = []

    class CutoutLengthTestOperator(bpy.types.Operator):
        bl_idname = "anyimage.test_cutout_length"
        bl_label = "Test Cutout Length"
        edge_length: properties.cutout_edge_length_property()

        def execute(self, context):
            captured.append(self.edge_length)
            return {"FINISHED"}

    units = bpy.context.scene.unit_settings
    previous = units.scale_length
    bpy.utils.register_class(CutoutLengthTestOperator)
    try:
        units.scale_length = 0.01
        bpy.ops.anyimage.test_cutout_length(edge_length=20)
        assert captured == pytest.approx([20])
    finally:
        units.scale_length = previous
        bpy.utils.unregister_class(CutoutLengthTestOperator)


def test_effective_length_report_and_geometry_build_share_value():
    report = Mock()
    context = SimpleNamespace(scene=SimpleNamespace(unit_settings=SimpleNamespace(system="METRIC", scale_length=0.01)))
    source = object()
    content = np.ones((10, 10))
    with patch.object(operators, "effective_cutout_edge_length", return_value=20), \
         patch.object(operators, "build_base_shape") as build, \
         patch.object(operators, "create_shape_object") as create, \
         patch.object(operators.bpy.ops.ed, "undo_push", return_value={"FINISHED"}):
        operators.create_cutout_shape(
            context,
            source,
            "FLAT",
            10,
            content,
            (0, 0, 10, 10),
            boundary_padding=0.0,
            color_image=object(),
            report=report,
        )
    assert build.call_args.args[2] == 20
    assert create.call_args.args[0] is context
    assert create.call_args.args[1] is source
    assert create.call_args.args[2] == "FLAT"
    assert create.call_args.args[3] is content
    assert report.call_args.args[0] == {"INFO"}
    assert "20 cm" in report.call_args.args[1]
