import numpy as np
import pytest

from tests.anyimage.server.support import load_server_module


@pytest.mark.parametrize("dtype", [np.uint8, np.float32])
def test_model_rgb_is_independent_of_visible_opacity(tmp_path, dtype):
    media = load_server_module("media.input")
    pixels = np.array([[[24, 65, 192, 128], [99, 99, 99, 0]]], np.uint8)
    path = tmp_path / "input.npy"
    np.save(path, pixels if dtype == np.uint8 else pixels.astype(np.float32) / 255)
    np.testing.assert_array_equal(media.load_ai_input(path, as_bytes=True), pixels)
    np.testing.assert_allclose(media.load_ai_input(path), pixels / 255, atol=1e-7)


@pytest.mark.parametrize("pixels", [
    np.zeros((2, 2, 3), np.uint8), np.zeros((0, 1, 4), np.uint8),
    np.zeros((1, 2, 4), np.uint16), np.zeros((1, 2, 4), object),
    *(np.full((1, 1, 4), value, np.float32) for value in (-1, 2, np.nan, np.inf)),
])
def test_invalid_array_is_rejected(tmp_path, pixels):
    path = tmp_path / "input.npy"
    np.save(path, pixels)
    with pytest.raises(ValueError):
        load_server_module("media.input").load_ai_input(path)


def test_archive_and_unreadable_input_are_rejected(tmp_path):
    media = load_server_module("media.input")
    archive = tmp_path / "archive.npz"
    np.savez(archive, image=np.zeros((1, 1, 4), np.uint8))
    with pytest.raises(ValueError, match="single RGBA"):
        media.load_ai_input(archive)
    with pytest.raises(ValueError, match="Unable to read") as failure:
        media.load_ai_input(tmp_path / "missing.npy")
    assert isinstance(failure.value.__cause__, OSError)
