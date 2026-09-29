import hashlib
import http.client
import os
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import (
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
    urlopen,
)

HF_ENDPOINT = "https://huggingface.co"
R2_ENDPOINT = "https://models.omoolab.xyz"
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
DOWNLOAD_CHUNK_SIZE = 256 * 1024


class _ShortConnectHTTPSConnection(http.client.HTTPSConnection):
    """Bound connection and idle reads without limiting total download time."""

    def connect(self):
        try:
            self.timeout = CONNECT_TIMEOUT
            super().connect()
        finally:
            self.timeout = None
        self.sock.settimeout(READ_TIMEOUT)


class _ShortConnectHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_ShortConnectHTTPSConnection, request)


_download_opener = build_opener(ProxyHandler(), _ShortConnectHTTPSHandler())


class DownloadProgressReporter:
    def __init__(self, progress_callback, label, clock=time.monotonic):
        self.progress_callback = progress_callback
        self.label = label
        self.clock = clock
        self.progress = 0.05
        self.last_write_time = 0.0
        self.started_at = clock()

    def report(self, current, total):
        if not total or current <= 0:
            return
        factor = min(current / total, 1.0)
        progress = 0.05 + factor * 0.90
        now = self.clock()
        if progress <= self.progress or (
            now - self.last_write_time < 0.20 and factor < 1.0
        ):
            return
        self.progress = progress
        self.last_write_time = now
        elapsed = now - self.started_at
        speed = f" {format_rate(current / elapsed)}" if elapsed > 0 else ""
        self.progress_callback(progress, f"Downloading {self.label}{speed}")


def download_model(model, model_dir, progress, cancel_check):
    """Download the catalog files from Hugging Face, then the R2 mirror."""
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    if model.huggingface_repository:
        sources.append((
            HF_ENDPOINT,
            lambda filename: hf_file_url(model.huggingface_repository, filename),
            model.label,
        ))
    sources.append((
        R2_ENDPOINT,
        lambda filename: r2_file_url(model.r2_directory, filename),
        f"{model.label} (mirror)",
    ))
    failures = []
    for source, url_builder, label in sources:
        cancel_check()
        progress(0.05, f"Downloading {label}")
        try:
            _download_declared_files(
                model.files, model_dir, url_builder, progress, cancel_check, label,
            )
        except Exception as error:
            cancel_check()
            failures.append((source, error))
            continue
        progress(0.95, f"{model.label} ready")
        return
    detail = "; ".join(f"{source}: {error}" for source, error in failures)
    raise RuntimeError(f"All download sources failed: {detail}")


def _download_file_from_url(
    url,
    destination,
    expected_size,
    expected_checksum,
    progress=None,
    cancel_check=None,
):
    """Download and verify one model file atomically from a direct URL."""
    request = Request(url, headers={"User-Agent": "AnyImage"})
    opener = _download_opener.open if request.type == "https" else urlopen
    temporary = destination.with_name(f"{destination.name}.part")
    try:
        checksum = hashlib.sha256()
        downloaded = 0
        with opener(request) as response:
            with open(temporary, "wb") as output:
                while True:
                    if cancel_check is not None:
                        cancel_check()
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    checksum.update(chunk)
                    downloaded += len(chunk)
                    if progress is not None:
                        progress(len(chunk))
        if downloaded != expected_size:
            raise RuntimeError(
                f"Size mismatch for {destination.name}: "
                f"{downloaded} != {expected_size}"
            )
        if checksum.hexdigest().lower() != expected_checksum.lower():
            raise RuntimeError(f"SHA-256 mismatch for {destination.name}")
        temporary.replace(destination)
        return
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def r2_file_url(directory, filename):
    return f"{R2_ENDPOINT}/{quote(directory)}/{quote(filename)}"


def hf_file_url(repository, filename):
    """Hugging Face resolve URL for a direct, metadata-free download."""
    endpoint = (os.environ.get("HF_ENDPOINT") or HF_ENDPOINT).rstrip("/")
    return f"{endpoint}/{repository}/resolve/main/{quote(filename)}"


def _download_declared_files(files, model_dir, url_builder, progress, cancel_check, label):
    reporter = DownloadProgressReporter(progress, label)
    total_size = sum(size for _path, size, _checksum in files)
    downloaded = 0

    def on_chunk(count):
        nonlocal downloaded
        downloaded += count
        reporter.report(downloaded, total_size)

    for path, size, checksum in files:
        destination = model_dir / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        _download_file_from_url(
            url_builder(path), destination, size, checksum,
            progress=on_chunk, cancel_check=cancel_check,
        )


def format_rate(rate):
    size = float(rate)
    if size <= 0:
        return ""
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{size:.0f} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"
