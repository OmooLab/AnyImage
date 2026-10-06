from unittest.mock import patch

import numpy as np

from server.models import onnx_moge3
from server import model_catalog


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
        output, options = onnx_moge3.infer(
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


def test_moge3_catalog_uses_onnx_assets_and_geometry_family():
    model = model_catalog.get_downloadable_model("MOGE3_VITL")
    assert tuple(name for name, _, _ in model.files) == ("backbone.onnx", "refiner.onnx")
    assert model_catalog.model_record(model)["family"] == "moge"
    assert model.huggingface_repository == ""
