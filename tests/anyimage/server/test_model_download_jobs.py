import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from tests.anyimage.server.support import load_server_module


class ModelDownloadJobsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.download = load_server_module("model_download")


    def test_download_model_uses_actual_request_without_preflight(self):
        calls = []
        fake_hugging_face = ModuleType("huggingface_hub")
        fake_hugging_face.snapshot_download = lambda **options: calls.append(
            options
        )
        args = SimpleNamespace(
            repository="Ruicheng/moge-2-vits-normal-onnx",
            model_dir="model",
            progress=lambda *_args, **_kwargs: None,
            allow_pattern=[],
        )

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"huggingface_hub": fake_hugging_face},
        ), patch.object(
            self.download,
            "create_download_progress_class",
            return_value=object,
        ), patch.dict(os.environ, {"HF_ENDPOINT": ""}), patch.object(
            self.download,
            "_verify_model_complete",
            return_value=None,
        ):
            args.model_dir = str(Path(directory) / "models" / "MoGe2")
            self.download.download_model(args)

        self.assertEqual(len(calls), 1)


    def test_download_model_refuses_success_when_files_missing(self):
        fake_hugging_face = ModuleType("huggingface_hub")
        fake_hugging_face.snapshot_download = lambda **options: None
        args = SimpleNamespace(
            repository="PramaLLC/BEN2",
            model_dir="model",
            progress=lambda *_args, **_kwargs: None,
            allow_pattern=[],
        )

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"huggingface_hub": fake_hugging_face},
        ), patch.object(
            self.download,
            "create_download_progress_class",
            return_value=object,
        ), patch.dict(os.environ, {"HF_ENDPOINT": ""}):
            args.model_dir = str(Path(directory) / "model")
            with self.assertRaisesRegex(
                RuntimeError,
                "All download sources failed",
            ):
                self.download.download_model(args)


    def test_download_model_reports_all_failed_sources(self):
        args = SimpleNamespace(
            repository="Ruicheng/moge-2-vits-normal-onnx",
            model_dir="model",
            progress=lambda *_args, **_kwargs: None,
            allow_pattern=[],
            r2_directory="moge-2-vits-normal-onnx",
            r2_file=["config.json|100|abc"],
        )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            self.download,
            "download_from_hf",
            side_effect=OSError("direct down"),
        ), patch.object(
            self.download,
            "download_from_r2",
            side_effect=OSError("mirror down"),
        ):
            args.model_dir = str(Path(directory) / "model")
            with self.assertRaisesRegex(RuntimeError, "models.omoolab.xyz"):
                self.download.download_model(args)


    def test_download_model_prefers_direct_hf_then_r2(self):
        args = SimpleNamespace(
            repository="Ruicheng/moge-2-vits-normal-onnx",
            model_dir="model",
            progress=lambda *_args, **_kwargs: None,
            allow_pattern=["config.json"],
            r2_directory="moge-2-vits-normal-onnx",
            r2_file=["config.json|100|abc"],
        )
        order = []

        def fake_download_from_hf(*_args, **_kwargs):
            order.append("hf")
            raise OSError("hf down")

        def fake_download_from_r2(*_args, **_kwargs):
            order.append("r2")

        with tempfile.TemporaryDirectory() as directory, patch.object(
            self.download,
            "download_from_hf",
            side_effect=fake_download_from_hf,
        ), patch.object(
            self.download,
            "download_from_r2",
            side_effect=fake_download_from_r2,
        ), patch.object(
            self.download,
            "_verify_model_complete",
            return_value=None,
        ):
            args.model_dir = str(Path(directory) / "models" / "MoGe2")
            self.download.download_model(args)

        self.assertEqual(order, ["hf", "r2"])


    def test_download_from_r2_downloads_declared_files(self):
        args = SimpleNamespace(
            repository="Ruicheng/moge-2-vits-normal-onnx",
            model_dir="model",
            progress=lambda *_args, **_kwargs: None,
            allow_pattern=["config.json"],
            r2_directory="moge-2-vits-normal-onnx",
            r2_file=["config.json|100|abc"],
        )
        downloaded = []

        with tempfile.TemporaryDirectory() as directory, patch.object(
            self.download,
            "_download_file_from_url",
            side_effect=lambda *args, **kwargs: downloaded.append(args[1].name),
        ):
            args.model_dir = str(Path(directory) / "model")
            self.download.download_from_r2(args, args.model_dir)

        self.assertEqual(downloaded, ["config.json"])
