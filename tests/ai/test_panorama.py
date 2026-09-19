"""Analytic projection, production inference and artifact lifecycle checks."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from tests.anyimage.server.support import FakeJobContext, load_server_module

geometry = load_server_module("geometry.panorama")
onnx = load_server_module("models.onnx_moge2")
job = load_server_module("jobs.panorama")


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
    prediction = onnx.postprocess(raw, fov_x=90, source_valid=visible)
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
    context = FakeJobContext(tmp_path / "result", "generate-panorama-geometry",
                             SimpleNamespace(directory=lambda _: tmp_path, get_moge=lambda *_: object()))
    calls, pixels = [], []

    def infer(session, color, level, **options):
        calls.append((color, level, options))
        rays = geometry.view_rays(color.shape[0])
        points = rays / np.linalg.norm(rays, axis=-1, keepdims=True) * 3
        return {"points": points, "mask": np.ones(color.shape[:2])}

    monkeypatch.setattr(job, "infer", infer)
    write = job.write_float_exr
    monkeypatch.setattr(job, "write_float_exr", lambda rgba, path: (pixels.append(rgba.copy()), write(rgba, path))[1])
    parameters = {"input": str(source), "model": "MOGE2", "device": "cpu", "resolution_level": 3,
                  "max_input_size": 32}
    return source, context, parameters, calls, pixels


def test_job_outputs_geometry_combines_alpha_once_and_skips_transparent_views(panorama_job):
    source, context, parameters, calls, pixels = panorama_job
    image = np.full((32, 64, 4), 255, np.uint8)
    image[:24, :, 3] = 0
    image[26:28, :, 3] = 128
    Image.fromarray(image).save(source)
    result = job.run(context, parameters)
    assert 0 < len(calls) < 12
    assert all(level == 3 and opts["fov_x"] == 90 for _, level, opts in calls)
    assert all(np.all(color[~opts["source_valid"]] == 0) for color, _, opts in calls)
    assert {path.name for path in context.directory.iterdir()} == {"depth.exr", "depth.json"}
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


@pytest.mark.parametrize("kind", ["transparent", "invalid_model", "wrong_ratio", "cancel"])
def test_failed_jobs_leave_no_partial_artifacts(panorama_job, monkeypatch, kind):
    source, context, parameters, calls, _ = panorama_job
    Image.new("RGBA", (64 if kind != "wrong_ratio" else 32, 32),
              (255, 255, 255, 0 if kind == "transparent" else 255)).save(source)
    if kind == "invalid_model":
        monkeypatch.setattr(job, "infer", lambda *a, **k: {"points": np.ones((32, 32, 3)), "mask": np.zeros((32, 32))})
    if kind == "cancel":
        count = [0]
        def cancel():
            count[0] += 1
            if count[0] == 6:
                raise RuntimeError("Cancelled")
        context.check_cancelled = cancel
    with pytest.raises((ValueError, RuntimeError)):
        job.run(context, parameters)
    assert not list(context.directory.glob("depth.*"))
    assert not (context.directory / "foreground.png").exists()
    if kind == "transparent":
        assert not calls
