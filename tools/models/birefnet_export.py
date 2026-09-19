# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = [
#   "torch==2.13.0", "torchvision==0.28.0", "onnx==1.22.0",
#   "numpy==2.4.6", "transformers==4.57.6", "timm==1.0.25",
#   "kornia==0.8.2", "einops==0.8.2", "safetensors==0.7.0",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch" }
# torchvision = { index = "pytorch" }
# [[tool.uv.index]]
# name = "pytorch"
# url = "https://download.pytorch.org/whl/cu130"
# explicit = true
# ///
"""Export pinned official BiRefNet weights to fixed-resolution ONNX alpha."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import onnx
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForImageSegmentation

from onnx_weights import compress_weights, compress_exact_constants
from deform_sampling import deform_conv, validate_deform


SOURCES = {
    "lite": ("ZhengPeng7/BiRefNet_lite", "aa62cd87eafb9cc43056d08ef3615a14628b831d", 1024),
    "hr-matting": ("ZhengPeng7/BiRefNet_HR-matting", "5d6b6f8adcb5b417c871b1d84ceaae9871355b7f", 2048),
}
WEIGHT_HASHES = {
    "lite": "4417d89795250e698c3cb0ae8df15743810065f646f48a694fdfa7ca052d0815",
    "hr-matting": "a5a4de698739ea5e0e8bbab28e1b293dde95092b87a442d566cbc585c53cef55",
}
LICENSE_REVISION = "ebcc0bc8ec7fe919cec829f2dea656b3078acddc"


class AlphaModel(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, image):
        return self.model(image)[-1].sigmoid()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=SOURCES, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--fp32-output", type=Path)
    args = parser.parse_args()
    repository, revision, size = SOURCES[args.variant]
    checkpoint = args.checkpoint / "model.safetensors" if args.checkpoint else Path(
        hf_hub_download(repository, "model.safetensors", revision=revision)
    )
    with checkpoint.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != WEIGHT_HASHES[args.variant]:
            raise RuntimeError("BiRefNet checkpoint SHA-256 mismatch")
    torch.set_num_threads(8)
    model = AutoModelForImageSegmentation.from_pretrained(
        str(args.checkpoint) if args.checkpoint else repository,
        revision=revision,
        trust_remote_code=True,
    ).eval()
    validate_deform()
    sys.modules[type(model).__module__].deform_conv2d = deform_conv
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AlphaModel(model).to(device)
    args.destination.mkdir(parents=True, exist_ok=True)
    output = args.destination / "model.onnx"
    with torch.inference_mode():
        torch.onnx.export(
            model, torch.zeros(1, 3, size, size, device=device),
            str(output),
            input_names=["image"], output_names=["alpha"],
            opset_version=17, dynamo=False, do_constant_folding=False,
        )
    graph = onnx.load(output)
    if args.fp32_output:
        onnx.save(graph, args.fp32_output)
    compress_weights(graph)
    compress_exact_constants(graph)
    onnx.checker.check_model(graph)
    onnx.save(graph, output)
    license_url = f"https://raw.githubusercontent.com/ZhengPeng7/BiRefNet/{LICENSE_REVISION}/LICENSE"
    license_text = urlopen(license_url, timeout=60).read()
    if hashlib.sha256(license_text).hexdigest() != "92a7089e0915fc32bc40067560b398f1e6a7a5958abd7d04eda393629a5acefb":
        raise RuntimeError("BiRefNet license SHA-256 mismatch")
    (args.destination / "LICENSE.txt").write_bytes(license_text)
    with output.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    record = {"repository": repository, "revision": revision, "input_size": size,
              "bytes": output.stat().st_size, "sha256": checksum,
              "checkpoint_sha256": WEIGHT_HASHES[args.variant]}
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
