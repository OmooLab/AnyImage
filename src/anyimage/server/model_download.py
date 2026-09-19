import hashlib
import http.client
import os
import threading
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
    def __init__(
        self,
        progress_callback,
        repository,
        clock=time.monotonic,
        start=0.05,
        span=0.90,
        label=None,
    ):
        self.progress_callback = progress_callback
        self.repository = repository
        self.clock = clock
        self.lock = threading.Lock()
        self.start = start
        self.span = span
        self.label = label
        self.progress = start
        self.last_write_time = 0.0
        self.started_at = self.clock()

    def report(self, current, total, rate=None):
        if not total or current <= 0:
            return

        factor = min(max(current / total, 0.0), 1.0)
        progress = self.start + factor * self.span
        now = self.clock()
        with self.lock:
            if progress <= self.progress:
                return
            if now - self.last_write_time < 0.20 and factor < 1.0:
                return
            self.progress = progress
            self.last_write_time = now
            effective_rate = rate
            elapsed = now - self.started_at
            if not effective_rate and elapsed > 0:
                effective_rate = current / elapsed
            speed = format_rate(effective_rate) if effective_rate else ""
            prefix = self.label or self.repository
            message = f"Downloading {prefix}"
            if speed:
                message = f"{message} {speed}"
            self.progress_callback(
                progress,
                message,
            )


def create_download_progress_class(
    progress_callback,
    repository,
    tqdm_type=None,
    clock=time.monotonic,
    start=0.05,
    span=0.90,
    label=None,
):
    if tqdm_type is None:
        from tqdm.auto import tqdm as tqdm_type

    reporter = DownloadProgressReporter(
        progress_callback,
        repository,
        clock,
        start,
        span,
        label,
    )

    class DownloadProgress(tqdm_type):
        def __init__(self, *args, **kwargs):
            description = str(kwargs.get("desc", ""))
            # huggingface_hub 1.x 的字节进度条描述是 "Downloading (incomplete total...)"，
            # 用前缀匹配而非精确匹配，否则真实下载进度会被忽略。
            self.anyimage_reports_progress = (
                description.startswith("Downloading")
                or description.startswith("Fetching ")
            )
            super().__init__(*args, **kwargs)

        def update(self, amount=1):
            result = super().update(amount)
            if self.anyimage_reports_progress:
                reporter.report(self.n, self.total, self._download_rate())
            return result

        def refresh(self, *args, **kwargs):
            result = super().refresh(*args, **kwargs)
            if self.anyimage_reports_progress:
                reporter.report(self.n, self.total, self._download_rate())
            return result

        def _download_rate(self):
            try:
                return getattr(self, "format_dict", {}).get("rate")
            except Exception:
                return None

    return DownloadProgress


def progress_range(args):
    start = getattr(args, "progress_start", None)
    end = getattr(args, "progress_end", None)
    if start is not None and end is not None:
        return float(start), float(end) - float(start)
    return 0.05, 0.90


def download_model(args):
    label = getattr(args, "label", None) or args.repository
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    start, span = progress_range(args)
    r2_directory = getattr(args, "r2_directory", "")
    r2_files = getattr(args, "r2_file", [])
    if r2_directory and r2_files:
        _download_declared_or_fail(
            args,
            model_dir,
            label,
            start,
            span,
        )
        return
    _download_snapshot_or_fail(args, model_dir, label, start, span)


def _download_declared_or_fail(args, model_dir, label, start, span):
    """Download declared files from Hugging Face when available, then R2."""
    sources = []
    if args.repository:
        sources.append((HF_ENDPOINT, download_from_hf, f"Downloading {label}"))
    sources.append((
            R2_ENDPOINT,
            download_from_r2,
            f"Downloading {label} (mirror)",
    ))
    failures = []
    for source, downloader, message in sources:
        args.progress(start, message)
        try:
            downloader(
                args,
                model_dir,
                start=start,
                span=span,
                label=label,
            )
            _verify_model_complete(
                model_dir,
                getattr(args, "required_pattern", None),
            )
        except Exception as error:
            cancel_check = getattr(args, "cancel_check", None)
            if cancel_check is not None:
                cancel_check()
            failures.append((source, error))
            continue
        args.progress(start + span, f"{label} ready")
        return
    detail = "; ".join(
        f"{source}: {error}" for source, error in failures
    )
    raise RuntimeError(f"All download sources failed: {detail}")


def _download_snapshot_or_fail(args, model_dir, label, start, span):
    """Fallback download for repositories without declared files, via huggingface_hub."""
    failures = []
    try:
        from huggingface_hub import snapshot_download
    except Exception as error:
        snapshot_download = None
        failures.append((HF_ENDPOINT, error))
    progress_class = None
    if snapshot_download:
        progress_class = create_download_progress_class(
            args.progress,
            args.repository,
            start=start,
            span=span,
            label=label,
        )
    for endpoint in download_endpoints() if snapshot_download else ():
        os.environ["HF_ENDPOINT"] = endpoint
        # snapshot_download 先拉取文件清单并校验 ETag，还没有字节下载，
        # 用 Checking 提示当前阶段，避免进度条看起来卡住。
        message = f"Checking {label} files"
        if endpoint != HF_ENDPOINT:
            message = f"{message} (mirror)"
        args.progress(start, message)
        try:
            snapshot_download(
                repo_id=args.repository,
                local_dir=model_dir,
                tqdm_class=progress_class,
                allow_patterns=args.allow_pattern or None,
                endpoint=endpoint,
            )
            _verify_model_complete(
                model_dir,
                getattr(args, "required_pattern", None),
            )
        except Exception as error:
            cancel_check = getattr(args, "cancel_check", None)
            if cancel_check is not None:
                cancel_check()
            failures.append((endpoint, error))
            continue
        args.progress(start + span, f"{label} ready")
        return
    detail = "; ".join(
        f"{source}: {error}" for source, error in failures
    )
    raise RuntimeError(f"All download sources failed: {detail}")


def download_endpoints():
    """Return the configured Hugging Face endpoint or official source."""
    endpoint = os.environ.get("HF_ENDPOINT") or HF_ENDPOINT
    return [endpoint.rstrip("/")]


def _verify_model_complete(model_dir, required_patterns=None):
    """Refuse to report success when the required model files are missing."""
    model_dir = Path(model_dir)
    required_patterns = required_patterns or (
        "config.json",
        "*.safetensors",
    )
    missing = [
        pattern
        for pattern in required_patterns
        if not any(model_dir.glob(pattern))
    ]
    if missing:
        raise RuntimeError(
            "Model download reported success but files are missing: "
            + ", ".join(missing)
        )


def _download_file_from_url(
    url,
    destination,
    expected_size,
    expected_checksum,
    progress=None,
    retries=1,
    cancel_check=None,
):
    """Download and verify one model file atomically from a direct URL."""
    request = Request(url, headers={"User-Agent": "AnyImage"})
    opener = _download_opener.open if request.type == "https" else urlopen
    last_error = None
    for _attempt in range(retries):
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
        except Exception as error:
            if cancel_check is not None:
                cancel_check()
            last_error = error
            try:
                temporary.unlink()
            except OSError:
                pass
    raise last_error


def r2_file_url(directory, filename):
    return f"{R2_ENDPOINT}/{quote(directory)}/{quote(filename)}"


def hf_file_url(repository, filename):
    """Hugging Face resolve URL for a direct, metadata-free download."""
    endpoint = (os.environ.get("HF_ENDPOINT") or HF_ENDPOINT).rstrip("/")
    return f"{endpoint}/{repository}/resolve/main/{quote(filename)}"


def _parse_declared_files(args):
    selected = []
    for value in args.r2_file:
        filename, size, checksum = value.split("|", 2)
        selected.append((filename, int(size), checksum))
    return selected


def _download_declared_files(
    args,
    model_dir,
    url_builder,
    start,
    span,
    label,
    retries=1,
):
    """Download each declared file through url_builder with aggregated progress."""
    repository = args.repository
    selected = _parse_declared_files(args)
    reporter = DownloadProgressReporter(
        args.progress,
        repository,
        start=start,
        span=span,
        label=label or repository,
    )
    total_size = sum(size for _path, size, _checksum in selected)
    downloaded = 0

    def on_chunk(count):
        nonlocal downloaded
        downloaded += count
        reporter.report(downloaded, total_size)

    for path, size, checksum in selected:
        destination = Path(model_dir) / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        _download_file_from_url(
            url_builder(path),
            destination,
            size,
            checksum,
            progress=on_chunk,
            retries=retries,
            cancel_check=getattr(args, "cancel_check", None),
        )


def download_from_r2(
    args,
    model_dir,
    start=0.05,
    span=0.90,
    label=None,
):
    """Download the declared model files from OmooLab R2."""
    _download_declared_files(
        args,
        model_dir,
        lambda filename: r2_file_url(args.r2_directory, filename),
        start,
        span,
        f"{label} (mirror)" if label else "mirror",
    )


def download_from_hf(
    args,
    model_dir,
    start=0.05,
    span=0.90,
    label=None,
):
    """Download the declared model files directly from Hugging Face resolve URLs."""
    _download_declared_files(
        args,
        model_dir,
        lambda filename: hf_file_url(args.repository, filename),
        start,
        span,
        label,
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
