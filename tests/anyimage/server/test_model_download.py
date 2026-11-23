import hashlib
import io
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from server import model_catalog, model_download as download


def test_https_connection_bounds_connect_and_idle_read_time():
    connect_timeouts, read_timeouts = [], []

    def connect(connection):
        connect_timeouts.append(connection.timeout)
        connection.sock = SimpleNamespace(settimeout=read_timeouts.append)

    connection = download._ShortConnectHTTPSConnection("example.com")
    with patch.object(download.http.client.HTTPSConnection, "connect", new=connect):
        connection.connect()
    assert connect_timeouts == [10.0]
    assert read_timeouts == [60.0]
    assert connection.timeout is None


@pytest.mark.parametrize("mirror", (False, True))
def test_reports_aggregated_bytes_speed_and_throttles_intermediate_updates(mirror):
    times = iter((0.0, 1.0, 1.1, 1.15))
    reports = []
    reporter = download.DownloadProgressReporter(lambda value, message, **args: reports.append((value, message, args)), "MoGe", clock=lambda: next(times), mirror=mirror)
    reporter.report(25, 100)
    reporter.report(50, 100)
    reporter.report(100, 100)
    assert len(reports) == 2
    assert reports[0][0] == pytest.approx(0.275)
    template = "Downloading {item} (mirror) {rate}" if mirror else "Downloading {item} {rate}"
    assert reports[0][1:] == (template, {"item": "MoGe", "rate": "25 B/s"})
    assert reports[-1][0] == pytest.approx(0.95)


@pytest.mark.parametrize("endpoint", ("", "https://hf.example/"))
def test_hf_url_respects_endpoint_and_escapes_filename(monkeypatch, endpoint):
    monkeypatch.setenv("HF_ENDPOINT", endpoint)
    assert download.hf_file_url("owner/model", "onnx/model name.onnx") == f"{endpoint.rstrip('/') or download.HF_ENDPOINT}/owner/model/resolve/main/onnx/model%20name.onnx"


@pytest.mark.parametrize("failure", (None, "size", "checksum", "cancel"))
def test_atomic_file_download_verifies_bytes_and_removes_partial_file(tmp_path, failure):
    content = b"model bytes"
    destination = tmp_path / "model.onnx"
    destination.write_bytes(b"previous")
    checksum = hashlib.sha256(content).hexdigest()
    size = len(content)
    if failure == "size":
        size += 1
    if failure == "checksum":
        checksum = "invalid"

    def cancel():
        if failure == "cancel":
            raise RuntimeError("Cancelled")

    with patch.object(download._download_opener, "open", return_value=io.BytesIO(content)):
        if failure:
            with pytest.raises(RuntimeError):
                download._download_file_from_url("https://example.com/model", destination, size, checksum, cancel_check=cancel)
        else:
            download._download_file_from_url("https://example.com/model", destination, size, checksum, cancel_check=cancel)
    assert destination.read_bytes() == (b"previous" if failure else content)
    assert not destination.with_suffix(".onnx.part").exists()


@pytest.mark.parametrize("source", ("hf", "mirror", "r2_only", "failed", "cancel"))
def test_download_catalog_files_with_verified_fallback_and_cancellation(tmp_path, source):
    content = b"valid model"
    files = (("onnx/model.onnx", len(content), hashlib.sha256(content).hexdigest()),)
    model = replace(model_catalog.BEN2_MODEL, files=files, huggingface_repository="" if source == "r2_only" else "owner/model")
    urls = []
    cancelled = False

    def cancel():
        if cancelled:
            raise RuntimeError("Cancelled")

    def open_url(request):
        nonlocal cancelled
        urls.append(request.full_url)
        if source == "cancel":
            cancelled = True
            raise RuntimeError("Cancelled")
        if source == "failed":
            raise OSError("Unavailable")
        if source == "mirror" and request.full_url.startswith(download.HF_ENDPOINT):
            return io.BytesIO(b"corrupt data")
        return io.BytesIO(content)

    progress = Mock()
    with patch.object(download._download_opener, "open", side_effect=open_url):
        if source in ("failed", "cancel"):
            with pytest.raises(RuntimeError, match="All download sources failed" if source == "failed" else "Cancelled"):
                download.download_model(model, tmp_path, progress, cancel)
        else:
            download.download_model(model, tmp_path, progress, cancel)
            assert (tmp_path / "onnx/model.onnx").read_bytes() == content
            assert progress.call_args.args[0] == 0.95
    assert len(urls) == (2 if source in ("mirror", "failed") else 1)
    assert urls[0].startswith(download.R2_ENDPOINT if source == "r2_only" else download.HF_ENDPOINT)
    if source == "mirror":
        assert urls[1].startswith(download.R2_ENDPOINT)
