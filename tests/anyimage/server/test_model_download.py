import io
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from server import model_download as download


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


def test_reports_aggregated_bytes_speed_and_throttles_intermediate_updates():
    times = iter((0.0, 1.0, 1.1, 1.15))
    reports = []
    reporter = download.DownloadProgressReporter(lambda *args: reports.append(args), "MoGe", clock=lambda: next(times))
    reporter.report(25, 100)
    reporter.report(50, 100)
    reporter.report(100, 100)
    assert len(reports) == 2
    assert reports[0][0] == pytest.approx(0.275)
    assert reports[0][1] == "Downloading MoGe 25 B/s"
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
