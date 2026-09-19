
import pytest
from PIL import Image

from tests.anyimage.server.support import load_server_module


@pytest.fixture
def media():
    return load_server_module("media.input")


@pytest.mark.parametrize("suffix", [".PNG", ".JPG", ".webp", ".jpeg"])
def test_supported_format_is_case_insensitive(media, tmp_path, suffix):
    path = tmp_path / f"input{suffix}"
    path.touch()
    assert media.validate_input_path(path) == path


@pytest.mark.parametrize("suffix,kind", [(".png", "image"), (".mp4", "image")])
def test_missing_path_precedes_format_validation(media, tmp_path, suffix, kind):
    with pytest.raises(RuntimeError, match=f"Source {kind} file does not exist"):
        media.validate_input_path(tmp_path / f"missing{suffix}")


def test_image_decode_error_keeps_cause(media, tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"broken")
    with pytest.raises(RuntimeError, match="Unable to read image") as error:
        with media.open_image(path):
            pytest.fail("Broken image must not reach processing")
    assert isinstance(error.value.__cause__, OSError)


def test_processing_error_is_not_relabelled(media, tmp_path):
    path = tmp_path / "valid.png"
    Image.new("RGB", (2, 2)).save(path)
    failure = OSError("inference failed")
    with pytest.raises(OSError) as error:
        with media.open_image(path):
            raise failure
    assert error.value is failure




@pytest.mark.parametrize("suffix", [".mp4", ".mts", ".gif", ".tiff", ""])
def test_unsupported_formats_are_rejected(media, tmp_path, suffix):
    path = tmp_path / f"input{suffix}"
    path.touch()
    with pytest.raises(RuntimeError, match="Unsupported input format"):
        media.validate_input_path(path)


def test_frame_directory_is_rejected(media, tmp_path):
    Image.new("RGB", (2, 2)).save(tmp_path / "frame.png")
    with pytest.raises(RuntimeError, match="Source image file does not exist"):
        media.validate_input_path(tmp_path)


def test_animated_png_is_rejected(media, tmp_path):
    path = tmp_path / "animated.png"
    Image.new("RGB", (2, 2), "red").save(
        path, save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")], duration=100,
    )
    with pytest.raises(RuntimeError, match="Only still images"):
        with media.open_image(path):
            pytest.fail("Animated images must not reach processing")


def test_ai_tasks_support_cooperative_cancellation(media):
    with pytest.raises(media.TaskCancelled):
        media.check_cancelled(lambda: True)
    media.check_cancelled(lambda: False)
