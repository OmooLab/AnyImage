import hashlib
import io
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from server import model_catalog, model_download as download


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
