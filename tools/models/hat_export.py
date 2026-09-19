# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = ["torch==2.13.0", "onnx==1.19.0", "numpy==1.26.4", "einops==0.8.2", "gdown==6.2.0"]
# [tool.uv.sources]
# torch = { index = "pytorch" }
# [[tool.uv.index]]
# name = "pytorch"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Export the official HAT Sharper checkpoint with FP16 weight storage."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import gdown
import onnx
import torch

from onnx_weights import compress_weights


REVISION = "1638a9a822581657811867bf670717f8371fc3e5"
CHECKPOINT_SHA256 = "5800b67136006eb8cab3b4ed7c8d73b6a195bb18e6cc709b674f9aa069c00271"
SOURCE_URL = f"https://raw.githubusercontent.com/XPixelGroup/HAT/{REVISION}"


def load_model(checkpoint, cache):
    architecture = cache / "hat_arch.py"
    if not architecture.exists():
        architecture.write_bytes(urlopen(SOURCE_URL + "/hat/archs/hat_arch.py", timeout=60).read())
    if hashlib.sha256(architecture.read_bytes()).hexdigest() != "81d8cecf491975246c9ebb20480898c656f59de020f38b05daa68741e426117f":
        raise RuntimeError("HAT architecture SHA-256 mismatch")
    # Export only: remove BasicSR's training registry and use the equivalent
    # PyTorch initialization utilities. The official forward remains unchanged.
    source = architecture.read_text(encoding="utf-8")
    source = source.replace("from basicsr.utils.registry import ARCH_REGISTRY", "")
    source = source.replace("@ARCH_REGISTRY.register()", "")
    source = source.replace(
        "from basicsr.archs.arch_util import to_2tuple, trunc_normal_",
        "from torch.nn.modules.utils import _pair as to_2tuple\nfrom torch.nn.init import trunc_normal_",
    )
    namespace = {"__name__": "hat_arch"}
    exec(compile(source, str(architecture), "exec"), namespace)
    model = namespace["HAT"](
        upscale=4, in_chans=3, img_size=64, window_size=16,
        compress_ratio=3, squeeze_factor=30, conv_scale=0.01,
        overlap_ratio=0.5, img_range=1., depths=[6] * 6,
        embed_dim=180, num_heads=[6] * 6, mlp_ratio=2,
        upsampler="pixelshuffle", resi_connection="1conv",
    ).eval()
    with checkpoint.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != CHECKPOINT_SHA256:
            raise RuntimeError("HAT Sharper checkpoint SHA-256 mismatch")
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True)["params_ema"], strict=True)
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    cache = Path(__file__).resolve().parents[2] / ".model-cache" / "hat-sharper"
    cache.mkdir(parents=True, exist_ok=True)
    checkpoint = args.checkpoint or cache / "Real_HAT_GAN_sharper.pth"
    if not checkpoint.exists():
        gdown.download(id="1EioFq5-mKmv1uqta_Byd9cgXp9SU3zjj", output=str(checkpoint))
    torch.set_num_threads(8)
    torch.manual_seed(0)
    model = load_model(checkpoint, cache)
    args.destination.mkdir(parents=True, exist_ok=True)
    output = args.destination / "model.onnx"
    with torch.inference_mode():
        torch.onnx.export(model, torch.zeros(1, 3, 256, 256), str(output),
                          opset_version=17, input_names=["input"], output_names=["output"],
                          do_constant_folding=False, dynamo=False)
    graph = onnx.load(output)
    compress_weights(graph)
    onnx.checker.check_model(graph)
    onnx.save(graph, output)
    (args.destination / "LICENSE.txt").write_bytes(urlopen(SOURCE_URL + "/LICENSE", timeout=60).read())
    if sum(path.stat().st_size for path in args.destination.iterdir()) >= 60_000_000:
        raise RuntimeError("HAT asset exceeds 60 MB")
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    print(json.dumps({"bytes": output.stat().st_size, "sha256": digest,
                      "revision": REVISION, "checkpoint_sha256": CHECKPOINT_SHA256}), flush=True)


if __name__ == "__main__":
    main()
