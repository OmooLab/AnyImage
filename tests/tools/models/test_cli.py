from tests.support.paths import PROJECT_ROOT
import importlib.util
import sys
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

import pytest


@pytest.mark.parametrize("command", ["prepare", "sync"])
def test_model_commands_prepare_all_before_upload(command):
    module = load_sync_models()
    events = []
    with (
        patch("sys.argv", ["model", command]),
        patch.object(module, "prepare_model", side_effect=lambda model: events.append(model)),
        patch.object(module, "upload_models", side_effect=lambda: events.append("upload")),
    ):
        module.main()
    assert events == [*module.MODEL_FILES, *(["upload"] if command == "sync" else [])]


def test_prepare_failure_prevents_upload():
    module = load_sync_models()
    with (
        patch("sys.argv", ["model", "sync"]),
        patch.object(module, "prepare_model", side_effect=RuntimeError("invalid model")),
        patch.object(module, "upload_models") as upload,
    ):
        with pytest.raises(RuntimeError, match="invalid model"):
            module.main()
    upload.assert_not_called()


def test_valid_model_cache_skips_all_preparation():
    module = load_sync_models()
    with (
        patch.object(module, "verify_file", return_value=True),
        patch.object(module, "build_model") as build,
        patch.object(module, "download_file") as download,
        patch.object(module.subprocess, "run") as run,
    ):
        for model in module.MODEL_FILES:
            module.prepare_model(model)
    build.assert_not_called()
    download.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("valid", [True, False])
def test_isolated_export_validates_all_outputs_before_replacing(tmp_path, valid):
    module = load_sync_models()
    digest = module.hashlib.sha256(b"new").hexdigest()
    models = tuple(module.ModelFile("HAT_GAN_X4_SHARPER", "hat-gan-x4-sharper", name, 3, digest) for name in ("a.onnx", "b.onnx"))

    def export(command, **kwargs):
        destination = Path(command[-1])
        (destination / "a.onnx").write_bytes(b"new")
        (destination / "b.onnx").write_bytes(b"new" if valid else b"bad")

    with patch.object(module, "MODELS_DIR", tmp_path), patch.object(module, "MODEL_FILES", models), patch.object(module.subprocess, "run", side_effect=export):
        models[1].destination.parent.mkdir()
        models[1].destination.write_bytes(b"old")
        if valid:
            module.prepare_model(models[0])
            assert all(model.destination.read_bytes() == b"new" for model in models)
        else:
            with pytest.raises(RuntimeError, match="SHA-256"):
                module.prepare_model(models[0])
            assert not models[0].destination.exists()
            assert models[1].destination.read_bytes() == b"old"
        assert not list(tmp_path.glob(".hat-gan-x4-sharper-*"))


def test_local_export_failure_cleans_temporary_output(tmp_path):
    module = load_sync_models()
    model = replace(next(model for model in module.MODEL_FILES if model.build), folder="test")

    def export(exporter, source, destination):
        destination.write_bytes(b"partial")
        raise RuntimeError("export failed")

    with (
        patch.object(module, "MODELS_DIR", tmp_path),
        patch.object(module, "PROJECT_ROOT", tmp_path),
        patch.object(module, "prepare_source", return_value=tmp_path / "weights.pth"),
        patch("tools.models.exports.export_model", side_effect=export),
    ):
        model.destination.parent.mkdir()
        model.destination.write_bytes(b"original")
        with pytest.raises(RuntimeError, match="export failed"):
            module.build_model(model)
        assert model.destination.read_bytes() == b"original"
        assert not model.destination.with_name(model.filename + ".part").exists()


def load_sync_models():
    path = PROJECT_ROOT / "tools" / "models" / "cli.py"
    spec = importlib.util.spec_from_file_location("sync_models", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyncModelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync = load_sync_models()

    def test_r2_is_only_an_upload_destination(self):
        for model in self.sync.MODEL_FILES:
            self.assertNotIn("models.omoolab.xyz", model.source_url)
            if model.build:
                self.assertFalse(model.source_url)

    def test_local_exports_use_official_pytorch_weights(self):
        builds = self.sync.MODEL_BUILDS
        self.assertEqual(
            set(builds),
            {"REALESRGAN_GENERAL_WDN_X4V3"},
        )
        for build in builds.values():
            self.assertTrue(build.source_url.startswith("https://github.com/"))
            self.assertTrue(build.source_filename.endswith(".pth"))
            self.assertEqual(len(build.source_sha256), 64)

    def test_prepare_model_builds_missing_local_export(self):
        model = next(model for model in self.sync.MODEL_FILES if model.build)
        with (
            patch.object(self.sync, "verify_file", return_value=False),
            patch.object(self.sync, "build_model") as build,
            patch.object(self.sync, "download_file") as download,
        ):
            self.sync.prepare_model(model)
        build.assert_called_once_with(model)
        download.assert_not_called()

    def test_prepare_model_downloads_upstream_onnx(self):
        model = next(
            model
            for model in self.sync.MODEL_FILES
            if model.source_url and not model.build
        )
        with (
            patch.object(self.sync, "verify_file", return_value=False),
            patch.object(self.sync, "download_file") as download,
        ):
            self.sync.prepare_model(model)
        download.assert_called_once_with(
            model.source_url,
            model.destination,
            model.size,
            model.sha256,
        )

    def test_upload_copies_declared_files_without_remote_deletion(self):
        model = self.sync.ModelFile(
            key="TEST",
            folder="folder",
            filename="model.onnx",
            size=1,
            sha256="hash",
        )
        with (
            patch.object(self.sync.shutil, "which", return_value="rclone"),
            patch.object(self.sync.subprocess, "run") as run,
        ):
            self.sync.upload_models((model,))
        command = run.call_args.args[0]
        self.assertEqual(command[1], "copyto")
        self.assertNotIn("sync", command)
        self.assertEqual(command[-2], model.remote)

    def test_verify_file_checks_size_and_sha256(self):
        path = PROJECT_ROOT / "tools" / "models" / "cli.py"
        size = path.stat().st_size
        digest = self.sync.file_sha256(path)
        self.assertTrue(self.sync.verify_file(path, size, digest))
        with self.assertRaisesRegex(RuntimeError, "unexpected size"):
            self.sync.verify_file(path, size - 1, digest)


if __name__ == "__main__":
    unittest.main()
