from tests.support.paths import PROJECT_ROOT
import os
import sys
import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


def load_download_module():
    addon_directory = PROJECT_ROOT / "src" / "anyimage"
    sys.path.insert(0, str(addon_directory))
    try:
        return __import__(
            "server.model_download",
            fromlist=["model_download"],
        )
    finally:
        sys.path.remove(str(addon_directory))


class FakeTqdm:
    def __init__(self, *args, **kwargs):
        self.n = kwargs.get("initial", 0)
        self.total = kwargs.get("total", 0)

    def update(self, amount=1):
        self.n += amount
        return True

    def refresh(self, *args, **kwargs):
        return True


class ModelDownloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.download = load_download_module()

    def create_progress(self, description="Downloading bytes", **options):
        reports = []
        progress_class = self.download.create_download_progress_class(
            lambda value, message: reports.append((value, message)),
            "owner/model",
            tqdm_type=options.pop("tqdm_type", FakeTqdm),
            clock=options.pop("clock", lambda: 1.0),
            **options,
        )
        progress = progress_class(
            desc=description,
            total=100,
            initial=0,
            unit="B",
        )
        return progress, reports

    def test_https_connection_bounds_connect_and_idle_read_time(self):
        connect_timeouts = []
        read_timeouts = []

        def connect(connection):
            connect_timeouts.append(connection.timeout)
            connection.sock = SimpleNamespace(
                settimeout=read_timeouts.append,
            )

        connection = self.download._ShortConnectHTTPSConnection("example.com")
        with patch.object(
            self.download.http.client.HTTPSConnection,
            "connect",
            new=connect,
        ):
            connection.connect()

        self.assertEqual(connect_timeouts, [10.0])
        self.assertEqual(read_timeouts, [60.0])
        self.assertIsNone(connection.timeout)

    def test_reports_aggregated_download_bytes(self):
        progress, reports = self.create_progress()

        progress.update(25)

        self.assertAlmostEqual(reports[-1][0], 0.275)
        self.assertEqual(reports[-1][1], "Downloading owner/model")

    def test_reports_hugging_face_aggregated_bar(self):
        progress, reports = self.create_progress(
            "Downloading (incomplete total...)"
        )

        progress.update(25)

        self.assertAlmostEqual(reports[-1][0], 0.275)

    def test_reports_download_speed(self):
        class FakeTqdmWithRate(FakeTqdm):
            @property
            def format_dict(self):
                return {"rate": 14_000_000}

        progress, reports = self.create_progress(
            tqdm_type=FakeTqdmWithRate,
            label="MoGe-2",
        )

        progress.update(50)

        self.assertEqual(
            reports[-1][1],
            "Downloading MoGe-2 13.4 MB/s",
        )

    def test_progress_callback_has_no_eta_or_state_protocol(self):
        times = iter((0.0, 10.0))
        progress, reports = self.create_progress(clock=lambda: next(times))

        progress.update(50)

        self.assertEqual(len(reports[-1]), 2)

    def test_ignores_unrelated_progress_bars(self):
        progress, reports = self.create_progress("Reconstructing")

        progress.update(25)

        self.assertEqual(reports, [])

    def test_download_endpoints_uses_direct_endpoint(self):
        with patch.dict(os.environ, {"HF_ENDPOINT": ""}):
            endpoints = self.download.download_endpoints()

        self.assertEqual(endpoints, ["https://huggingface.co"])

    def test_download_endpoints_respects_environment_override(self):
        with patch.dict(os.environ, {"HF_ENDPOINT": "https://hf.example"}):
            endpoints = self.download.download_endpoints()

        self.assertEqual(endpoints, ["https://hf.example"])

    def test_download_endpoints_strips_trailing_slash(self):
        with patch.dict(os.environ, {"HF_ENDPOINT": "https://hf.example/"}):
            endpoints = self.download.download_endpoints()

        self.assertEqual(endpoints, ["https://hf.example"])

    def test_declared_download_skips_hf_when_no_public_onnx_exists(self):
        args = SimpleNamespace(
            repository="",
            progress=lambda *_args: None,
            cancel_check=lambda: None,
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(
            self.download, "download_from_hf"
        ) as hugging_face, patch.object(
            self.download, "download_from_r2"
        ) as mirror, patch.object(
            self.download, "_verify_model_complete"
        ):
            self.download._download_declared_or_fail(
                args, Path(directory), "Model", 0.05, 0.90
            )

        hugging_face.assert_not_called()
        mirror.assert_called_once()


if __name__ == "__main__":
    unittest.main()
