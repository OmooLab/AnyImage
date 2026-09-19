from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest

from server.models import moge, onnx_moge3
from server import model_catalog, model_manager


def test_sparse_neighbors_and_pooling_follow_voxel_coordinates():
    coord = np.zeros((1, 16, 32, 3), dtype=np.float32)
    inputs = onnx_moge3.build_sparse_inputs(coord)
    neighbors = inputs["neighbor_0"]
    assert np.array_equal(neighbors[:, 13], np.arange(512))
    assert neighbors[0, 10] == 512  # Missing pixel at x=-1.
    assert neighbors[0, 16] == 1
    for level in range(4):
        children = inputs[f"pool_{level}"]
        parent = inputs[f"up_{level}"]
        for row, values in enumerate(children):
            valid = values < len(parent)
            assert np.all(parent[values[valid]] == row)
    shifted = coord.copy()
    shifted[..., 2] += 1
    for key, values in inputs.items():
        assert np.array_equal(values, onnx_moge3.build_sparse_inputs(shifted)[key])


def test_inference_runs_three_refinements_and_preserves_image_dimensions():
    calls = []
    coord = np.zeros((1, 16, 16, 3), dtype=np.float32)
    backbone = object()
    refiner = object()

    def run(session, names, inputs, *, release_memory):
        calls.append((session, inputs.copy(), release_memory))
        if session is backbone:
            return [
                coord,
                np.zeros((1, 1026, 1, 1), np.float32),
                np.ones((1, 3, 16, 16), np.float32),
                np.ones((1, 1, 16, 16), np.float32),
                np.zeros((1, 1), np.float32),
            ]
        assert "neighbor_4" in inputs
        return [np.full((1, 16, 16), 0.1, np.float32)]

    with (
        patch.object(onnx_moge3, "run_session", side_effect=run),
        patch.object(
            onnx_moge3,
            "postprocess",
            side_effect=lambda value, **kwargs: (value, kwargs),
        ),
    ):
        output, options = moge.infer_image(
            onnx_moge3.Moge3Session(backbone, refiner),
            np.zeros((7, 11, 3), np.float32),
            9,
            fov_x=90,
        )
    assert len(calls) == 4
    assert calls[0][1]["num_tokens"] == 3600
    assert [call[2] for call in calls[1:]] == [False, False, True]
    assert output["points"].shape == (1, 7, 11, 3)
    assert np.allclose(output["points"][..., 2], np.exp(0.3))
    assert options["fov_x"] == 90


def test_bilinear_resize_preserves_edges_and_pixel_centers():
    image = np.array([[0, 2], [4, 6]], np.float32)
    assert np.array_equal(onnx_moge3._resize(image, 2, 2), image)
    assert onnx_moge3._resize(image, 1, 1)[0, 0] == 3


def test_moge3_requires_all_verified_model_files(tmp_path):
    model = replace(
        model_catalog.MOGE3_VITL,
        r2_files=(
            (
                "backbone.onnx",
                1,
                "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
            ),
            (
                "refiner.onnx",
                1,
                "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d",
            ),
        ),
    )
    manager = model_manager.ModelManager(tmp_path)
    directory = manager.directory("MOGE3_VITL")
    directory.mkdir()
    with patch.object(
        model_manager.model_catalog, "get_downloadable_model", return_value=model
    ):
        (directory / "backbone.onnx").write_bytes(b"a")
        assert not manager.ready("MOGE3_VITL")
        (directory / "refiner.onnx").write_bytes(b"b")
        assert manager.ready("MOGE3_VITL")
        (directory / "refiner.onnx").write_bytes(b"c")
        assert not manager.ready("MOGE3_VITL")


def test_cache_reuses_moge3_and_releases_it_when_switching():
    cache = model_manager.ModelSessionCache()
    session = onnx_moge3.Moge3Session(object(), object())
    with patch.object(onnx_moge3, "create_session", return_value=session) as load:
        assert cache.get_moge("moge-3-vitl-onnx", "cpu") is session
        assert cache.get_moge("moge-3-vitl-onnx", "cpu") is session
        load.assert_called_once()
    from server.models import onnx_moge2

    with patch.object(onnx_moge2, "create_session", return_value=object()):
        assert cache.get_moge("moge-2-vits-normal-onnx", "cpu") is not session
    cache.close()
    assert cache.moge_model is None


def test_moge3_catalog_uses_onnx_assets_and_geometry_family():
    model = model_catalog.get_downloadable_model("MOGE3_VITL")
    assert model.ready_patterns == ("backbone.onnx", "refiner.onnx")
    assert model_catalog.model_record(model)["family"] == "moge"
    assert model.huggingface_repository == ""


def test_cache_recovers_after_moge3_session_load_failure():
    cache = model_manager.ModelSessionCache()
    session = onnx_moge3.Moge3Session(object(), object())
    with patch.object(
        onnx_moge3, "create_session", side_effect=[RuntimeError("load failed"), session]
    ):
        with pytest.raises(RuntimeError, match="load failed"):
            cache.get_moge("moge-3-vitl-onnx", "cpu")
        assert cache.moge_model is None
        assert cache.moge_key is None
        assert cache.get_moge("moge-3-vitl-onnx", "cpu") is session
