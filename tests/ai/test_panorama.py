"""Analytic projection, production inference and artifact lifecycle checks."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from tests.anyimage.server.support import FakeJobContext, load_server_module

geometry = load_server_module("geometry.panorama")
relief = load_server_module("geometry.panorama_relief")
onnx = load_server_module("models.onnx_moge2")
job = load_server_module("jobs.panorama")


def test_panorama_projection_preserves_asymmetric_source_pixels():
    image = np.arange(32 * 64, dtype=float).reshape(32, 64)
    sampled = geometry.sample_panorama(image, geometry.panorama_directions(64, 32))
    np.testing.assert_allclose(sampled, image, atol=1e-9)


def test_camera_normals_preserve_oblique_plane_and_ignore_invalid_samples():
    bases = geometry.camera_bases()
    expected = np.array((.2, -.3, .9))
    expected /= np.linalg.norm(expected)
    normals = [np.broadcast_to(expected @ basis.T, (64, 64, 3)).copy() for basis in bases]
    normals += [normal.copy() for normal in normals]
    bases = bases * 2
    masks = np.ones((24, 64, 64), bool)
    normals[0][:8] = np.nan
    normals[1][:8] = 0
    normals[2][:32] = (100, -500, 800)
    masks[2, :32] = False
    merged = geometry.merge_normals(normals, masks, bases, 128, 64)
    np.testing.assert_allclose(merged, np.broadcast_to(expected * (-1, 1, 1), merged.shape), atol=1e-6)


def test_panorama_relief_corrects_bias_and_preserves_periodic_detail():
    width, height = 1024, 512
    directions = geometry.panorama_directions(width, height) * (-1, 1, 1)
    reference = -directions
    tangent = np.cross((0, 0, 1), reference)
    tangent /= np.linalg.norm(tangent, axis=-1, keepdims=True)
    phase = 2 * np.pi * 180 * (np.arange(width) + .5) / width
    detail = .08 * np.sin(phase)
    native = .8 * reference + .6 * np.cross(reference, tangent) + detail[None, :, None] * tangent
    native = (native / np.linalg.norm(native, axis=-1, keepdims=True)).astype(np.float32)
    valid = np.zeros((height, width), bool)
    valid[height // 4:3 * height // 4] = True
    corrected, coverage = relief.refine_panorama_normals(np.full(valid.shape, 3, np.float32), native, valid)
    middle = slice(3 * height // 8, 5 * height // 8)
    np.testing.assert_allclose(np.linalg.norm(corrected, axis=-1), 1, atol=2e-6)
    assert np.min(np.sum(corrected[middle] * reference[middle], axis=-1)) > .98
    corrected_detail = np.sum(corrected[middle] * tangent[middle], axis=-1)
    recovery = np.mean(corrected_detail * detail) / np.mean(detail ** 2)
    assert recovery > .3
    np.testing.assert_allclose(corrected_detail[:, :128], corrected_detail[:, 256:384], atol=.008)
    assert not coverage[height // 4 - 1:height // 4 + 1].any()


def test_known_fov_recovers_shift_metric_and_excludes_invisible_points():
    rays = geometry.view_rays(64)
    depth = 2 + 0.3 * rays[..., 0]
    points = rays * depth[..., None]
    points[..., 2] -= 0.7
    visible = np.ones((64, 64), bool)
    visible[:8] = False
    points[:8] = np.nan
    raw = {"points": points[None], "normal": np.zeros_like(points)[None],
           "mask": np.ones((1, 64, 64)), "metric_scale": [1.5]}
    prediction = load_server_module("models.moge_geometry").postprocess(raw, fov_x=90, source_valid=visible)
    np.testing.assert_allclose(prediction["depth"][visible], depth[visible] * 1.5, rtol=1e-5)
    assert not prediction["mask"][:8].any()
    assert np.isfinite(prediction["points"]).all()


def test_periodic_fusion_removes_view_scale_offsets():
    bases = geometry.camera_bases()
    distances = []
    for scale, basis in zip(np.exp(np.linspace(-0.4, 0.4, 12)), bases):
        rays = geometry.view_rays(128) @ basis
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
        distances.append((3 + 0.4 * rays[..., 0] + 0.2 * rays[..., 2]) * scale)
    merged, valid = geometry.merge_distances(distances, np.ones((12, 128, 128), bool), bases, 64, 32)
    rays = geometry.panorama_directions(64, 32)
    expected = 3 + 0.4 * rays[..., 0] + 0.2 * rays[..., 2]
    merged *= np.median(expected / merged)
    assert valid.all()
    assert np.mean(abs(merged / expected - 1)) < 0.002
    assert np.max(abs(merged[:, [0, -1]] / expected[:, [0, -1]] - 1)) < 0.005
    sampled = geometry.sample_panorama(expected, np.array(((1, 1e-8, 0), (1, -1e-8, 0))))
    np.testing.assert_allclose(sampled[0], sampled[1], atol=1e-6)


@pytest.fixture
def panorama_job(tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    context = FakeJobContext(tmp_path / "result", "generate_panorama_geometry",
                             SimpleNamespace(directory=lambda _: tmp_path, get_session=lambda *_: (object(), 0.0)))
    calls, pixels = [], []

    def infer(session, color, level, **options):
        calls.append((color, level, options))
        rays = geometry.view_rays(color.shape[0])
        points = rays / np.linalg.norm(rays, axis=-1, keepdims=True) * 3
        return {"points": points, "normal": -points / 3, "mask": np.ones(color.shape[:2])}

    monkeypatch.setattr(onnx, "infer", infer)
    write = job.write_float_exr
    monkeypatch.setattr(job, "write_float_exr", lambda rgba, path: (pixels.append(rgba.copy()), write(rgba, path))[1])
    parameters = {"input": str(source), "model": "MOGE2_VITS_NORMAL", "device": "cpu", "resolution_level": 3,
                  "max_input_size": 128}
    return source, context, parameters, calls, pixels


def test_job_outputs_geometry_combines_alpha_once_and_skips_transparent_views(panorama_job):
    source, context, parameters, calls, pixels = panorama_job
    image = np.full((32, 64, 4), 255, np.uint8)
    image[:24, :, 3] = 0
    image[26:28, :, 3] = 128
    Image.fromarray(image.repeat(2, axis=0).repeat(2, axis=1)).save(source)
    parameters["max_input_size"] = 65
    result = job.run(context, parameters)
    assert 0 < len(calls) < 12
    assert all(level == 3 and opts["fov_x"] == 90 for _, level, opts in calls)
    assert all(np.all(color[~opts["source_valid"]] == 0) for color, _, opts in calls)
    assert result == {"depth": "depth.exr", "depth_metadata": "depth.json", "object_normal": "object-normal.png",
                      "normal_coverage": "normal-coverage.png"}
    assert {path.name for path in context.directory.iterdir()} == set(result.values())
    alpha = pixels[0][..., 3]
    assert pixels[0].shape == image.shape
    assert not alpha[:24].any()
    assert np.all(alpha <= image[..., 3] / 255 + 1e-7)
    assert np.any(np.isclose(alpha, 128 / 255))
    np.testing.assert_allclose(pixels[0][..., 0], pixels[0][..., 2])
    metadata = json.loads((context.directory / result["depth_metadata"]).read_text())
    assert metadata["projection"] == "equirectangular"
    assert metadata["image_size"] == [64, 32]
    assert set(metadata) == {"projection", "image_size"}
    for key in ("object_normal", "normal_coverage"):
        with Image.open(context.directory / result[key]) as texture:
            assert texture.size == (64, 32)


def test_job_writes_fused_depth_and_object_normals(panorama_job, monkeypatch):
    source, context, parameters, _, pixels = panorama_job
    width, height = 70, 35
    Image.new("RGBA", (width, height), (255, 255, 255, 255)).save(source)
    expected = np.array((.2, -.3, 1.0))
    expected /= np.linalg.norm(expected)
    directions = geometry.panorama_directions(width, height)
    facing = directions @ expected
    valid = facing < -.2
    distance = (-3 / np.minimum(facing, -.01)).astype(np.float32)
    monkeypatch.setattr(job, "merge_distances", lambda *args, **kwargs: (distance, valid))
    job.run(context, parameters)
    np.testing.assert_array_equal(pixels[0][..., 0], distance)
    np.testing.assert_array_equal(pixels[0][..., 3], valid)
    with Image.open(context.directory / "object-normal.png") as image:
        assert image.mode == "RGB"
        normal = np.asarray(image).astype(float) / 127.5 - 1
    inward = -directions * (-1, 1, 1)
    np.testing.assert_allclose(normal[~valid], inward[~valid], atol=1 / 255 + 1e-6)
    interior = facing < -.4
    interior[[0, -1]] = False
    expected_normal = expected * (-1, 1, 1)
    samples = normal[interior]
    samples /= np.linalg.norm(samples, axis=-1, keepdims=True)
    assert np.min(samples @ expected_normal) > np.cos(np.deg2rad(2))


def test_full_resolution_fusion_preserves_detail_and_periodic_alignment():
    bases = geometry.camera_bases()
    distances = []
    def radius(rays):
        angle = np.arctan2(rays[..., 1], rays[..., 0])
        return 3 + 0.15 * np.sin(80 * angle) * (1 - rays[..., 2] ** 2) ** 4
    for scale, basis in zip(np.exp(np.linspace(-0.2, 0.2, 12)), bases):
        rays = geometry.view_rays(512) @ basis
        rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
        distances.append(radius(rays) * scale)
    merged, valid = geometry.merge_distances(distances, np.ones((12, 512, 512), bool),
                                              bases, 1024, 512)
    expected = radius(geometry.panorama_directions(1024, 512))
    merged *= np.median(expected / merged)
    assert merged.shape == (512, 1024) and valid.all()
    assert np.sqrt(np.mean((merged - expected) ** 2)) < 0.001
    assert np.max(abs(merged[:, [0, -1]] / expected[:, [0, -1]] - 1)) < 0.01


def test_refinement_handles_partial_sky_coverage_and_cancellation():
    bases = geometry.camera_bases()
    rays = geometry.view_rays(64)
    masks, distances = [], []
    for basis in bases:
        directions = rays @ basis
        directions /= np.linalg.norm(directions, axis=-1, keepdims=True)
        masks.append(directions[..., 2] < .3)
        distances.append(np.full((64, 64), 3.0))
    merged, valid = geometry.merge_distances(distances, masks, bases, 1024, 512)
    assert valid.any() and not valid.all()
    assert np.isfinite(merged).all() and (merged > 0).all()
    np.testing.assert_allclose(merged[valid], 3, rtol=1e-5)
    checks = 0

    def cancel():
        nonlocal checks
        checks += 1
        if checks == 5:
            raise RuntimeError("Cancelled refinement")

    with pytest.raises(RuntimeError, match="Cancelled refinement"):
        geometry.merge_distances(distances, masks, bases, 1024, 512, cancel_check=cancel)
    assert checks == 5


@pytest.mark.parametrize("kind", ["transparent", "invalid_model", "wrong_ratio", "cancel", "metadata"])
def test_failed_jobs_leave_no_partial_artifacts(panorama_job, monkeypatch, kind):
    source, context, parameters, calls, _ = panorama_job
    Image.new("RGBA", (64 if kind != "wrong_ratio" else 32, 32),
              (255, 255, 255, 0 if kind == "transparent" else 255)).save(source)
    if kind == "invalid_model":
        def invalid_prediction(session, color, level, **options):
            return {"points": np.ones_like(color), "normal": np.zeros_like(color),
                    "mask": np.zeros(color.shape[:2])}

        monkeypatch.setattr(onnx, "infer", invalid_prediction)
    if kind == "metadata":
        def fail_metadata(*args, **kwargs):
            raise RuntimeError("Failed metadata serialization")
        monkeypatch.setattr(job, "json", SimpleNamespace(dumps=fail_metadata))
    if kind == "cancel":
        count = [0]
        def cancel():
            count[0] += 1
            if count[0] == 6:
                raise RuntimeError("Cancelled")
        context.check_cancelled = cancel
    with pytest.raises((ValueError, RuntimeError)):
        job.run(context, parameters)
    assert not list(context.directory.iterdir())
    if kind == "transparent":
        assert not calls
