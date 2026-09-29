import gc
import hashlib
import os
import weakref
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from server import model_catalog
from server.model_manager import ModelManager
from server.models import model_adapter, onnx_moge3
from server.models.onnx_runtime import OnnxResourceError


class Session:
    pass


@pytest.mark.parametrize("key", model_catalog.DOWNLOADABLE_MODELS)
def test_session_reuses_model_and_applies_catalog_device(tmp_path, key):
    manager = ModelManager(tmp_path)
    spec = model_catalog.get_downloadable_model(key)
    with patch.object(model_adapter(key), "create_session", return_value=Session()) as create:
        first, _ = manager.get_session(key, "directml")
        second, elapsed = manager.get_session(key, "directml")
    assert first is second
    assert elapsed == 0.0
    assert spec.label in manager.snapshot()["loaded"].values()
    create.assert_called_once_with(manager.directory(key), spec.device or "directml")
    manager.close()
    assert not any(manager.snapshot()["loaded"].values())


def test_switching_model_or_device_releases_previous_session_before_loading(tmp_path):
    manager = ModelManager(tmp_path)
    references = []

    def create(*args):
        assert all(ref() is None for ref in references)
        session = Session()
        references.append(weakref.ref(session))
        return session

    with patch.object(model_adapter("MOGE2_VITS_NORMAL"), "create_session", side_effect=create):
        manager.get_session("MOGE2_VITS_NORMAL", "cpu")
        manager.get_session("MOGE2_VITS_NORMAL", "directml")
        manager.get_session("MOGE2_VITB_NORMAL", "directml")
    assert len(references) == 3


def test_cache_keeps_three_families_and_only_replaces_selected_family(tmp_path):
    manager = ModelManager(tmp_path)
    keys = ("BEN2_BASE", "MOGE2_VITS_NORMAL", "REALESRGAN_X4PLUS")
    for key in keys:
        with patch.object(model_adapter(key), "create_session", side_effect=lambda *_: Session()):
            manager.get_session(key, "cpu")
    before = manager.snapshot()
    with patch.object(model_adapter("MOGE3_VITL"), "create_session", return_value=Session()):
        manager.get_session("MOGE3_VITL", "cpu")
    assert manager.snapshot()["loaded"] == {**before["loaded"], "geometry": "MoGe-3 ViT-L"}


@pytest.mark.parametrize("key", ("BEN2_BASE", "MOGE2_VITS_NORMAL", "REALESRGAN_X4PLUS"))
@pytest.mark.parametrize("error_type", (OnnxResourceError, MemoryError))
def test_resource_failure_releases_failed_frames_before_retry(tmp_path, key, error_type):
    manager = ModelManager(tmp_path)
    refs = []
    attempts = []

    def create(*args):
        attempts.append(True)
        if len(attempts) == 1:
            partial_session = Session()
            refs.append(weakref.ref(partial_session))
            raise error_type("allocation failed")
        assert refs[0]() is None
        assert not any(manager.snapshot()["loaded"].values())
        return Session()

    with patch.object(model_adapter(key), "create_session", side_effect=create):
        manager.get_session(key, "cpu")
    assert len(attempts) == 2


def test_failed_moge3_refiner_releases_backbone_even_while_error_is_retained(tmp_path):
    refs = []

    def create(path, device):
        if path.name == "backbone.onnx":
            result = Session()
            refs.append(weakref.ref(result))
            return result
        raise OnnxResourceError("refiner allocation failed")

    with patch.object(onnx_moge3, "create_runtime_session", side_effect=create):
        with pytest.raises(OnnxResourceError) as error:
            onnx_moge3.create_session(tmp_path)
    gc.collect()
    assert error.value is not None
    assert refs[0]() is None


@pytest.mark.parametrize("error_type, attempts", ((OnnxResourceError, 2), (RuntimeError, 1)))
def test_load_failure_has_bounded_retries_and_preserves_unrelated_cache(tmp_path, error_type, attempts):
    manager = ModelManager(tmp_path)
    with patch.object(model_adapter("BEN2_BASE"), "create_session", return_value=Session()):
        manager.get_session("BEN2_BASE", "cpu")
    with patch.object(model_adapter("MOGE3_VITL"), "create_session", side_effect=error_type("failed")) as create:
        with pytest.raises(error_type):
            manager.get_session("MOGE3_VITL", "cpu")
    assert create.call_count == attempts
    assert bool(manager.snapshot()["loaded"]["background"]) == (attempts == 1)
    assert manager.snapshot()["loaded"]["geometry"] == ""


@pytest.mark.parametrize("key", model_catalog.DOWNLOADABLE_MODELS)
def test_ready_checks_every_declared_file_and_same_size_corruption(tmp_path, key):
    spec = model_catalog.get_downloadable_model(key)
    content = b"verified"
    files = tuple((name, len(content), hashlib.sha256(content).hexdigest()) for name, _, _ in spec.files)
    spec = replace(spec, files=files)
    manager = ModelManager(tmp_path)
    with patch.object(model_catalog, "get_downloadable_model", return_value=spec):
        assert not manager.ready(key)
        for name, _, _ in files:
            path = manager.directory(key) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        assert manager.ready(key)
        path.write_bytes(b"damaged!")
        assert not manager.ready(key)


def test_verified_large_file_is_reused_until_identity_changes(tmp_path):
    content = b"a" * (1024 * 1024)
    spec = replace(model_catalog.BEN2_MODEL, files=(("model.onnx", len(content), hashlib.sha256(content).hexdigest()),))
    manager = ModelManager(tmp_path)
    directory = manager.directory(spec.key)
    directory.mkdir()
    path = directory / "model.onnx"
    path.write_bytes(content)
    os.utime(path, (1, 1))
    with patch.object(model_catalog, "get_downloadable_model", return_value=spec), patch.object(hashlib, "file_digest", wraps=hashlib.file_digest) as digest:
        assert manager.ready(spec.key)
        assert manager.ready(spec.key)
        assert digest.call_count == 1
        path.write_bytes(b"b" * len(content))
        assert not manager.ready(spec.key)


def test_required_downloads_skip_ready_models_and_aggregate_progress(tmp_path):
    manager = ModelManager(tmp_path)
    context = SimpleNamespace(progress=Mock())
    with patch.object(manager, "ready", side_effect=lambda key: key == "BEN2_BASE"), patch.object(manager, "_download") as download:
        result = manager.download_missing(context, ("BEN2_BASE", "MOGE3_VITL"))
    assert result == {"downloaded": ["MOGE3_VITL"]}
    assert download.call_args.args[1] == "MOGE3_VITL"
    download.call_args.args[2](0.5, "loading")
    context.progress.assert_called_once_with(0.5, "loading")
