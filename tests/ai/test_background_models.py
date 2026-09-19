import hashlib
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from server import model_catalog
from server.jobs import remove_background
from server.model_manager import ModelManager
from server.models import background
from tests.anyimage.server.support import FakeJobContext


@pytest.mark.parametrize("key", model_catalog.BACKGROUND_MODELS)
@pytest.mark.parametrize("kind", ["foreground", "alpha"])
def test_models_dispatch_keep_alpha(tmp_path, key, kind):
    source = tmp_path / "source.png"
    Image.new("RGBA", (7, 5), (60, 120, 180, 128)).save(source)
    manager = ModelManager(tmp_path / "models")
    context = FakeJobContext(tmp_path / "job", "remove-background", manager)
    adapter = background.model_adapter(manager.directory(key))
    parameters = {"input": str(source), "model": key, "device": "directml"}
    if kind == "alpha":
        parameters["output_kind"] = kind
    with patch.object(adapter, "create_session", return_value=object()) as create, patch.object(
        adapter, "infer_alpha", return_value=np.full((5, 7), .4, np.float32)
    ) as infer:
        remove_background.run(context, parameters)
    create.assert_called_once_with(manager.directory(key), "cpu" if key == "BIREFNET_HR_MATTING" else "directml")
    infer.assert_called_once()
    if kind == "alpha":
        np.testing.assert_allclose(np.load(context.directory / "alpha.npy"), .4)
    else:
        outputs = sorted(context.directory.glob("*.png"))
        assert len(outputs) == infer.call_count
        with Image.open(outputs[0]) as result:
            assert result.size == (7, 5)
            assert result.getpixel((0, 0)) == (60, 120, 180, 51)
    manager.close()
    assert manager.snapshot()["loaded"]["background"] == ""


@pytest.mark.parametrize("key", ["BIREFNET_LITE", "BIREFNET_HR_MATTING", "HAT_GAN_X4_SHARPER"])
def test_readiness_checks_model_and_license_corruption(tmp_path, key):
    from dataclasses import replace

    content = b"verified"
    files = tuple((name, len(content), hashlib.sha256(content).hexdigest()) for name in ("model.onnx", "LICENSE.txt"))
    spec = replace(model_catalog.get_downloadable_model(key), r2_files=files)
    directory = tmp_path / spec.directory_name
    directory.mkdir()
    manager = ModelManager(tmp_path)
    with patch.object(model_catalog, "get_downloadable_model", return_value=spec):
        assert not manager.ready(key)
        for name, _, _ in files:
            (directory / name).write_bytes(content)
        assert manager.ready(key)
        (directory / "LICENSE.txt").write_bytes(b"damaged!")
        assert not manager.ready(key)
