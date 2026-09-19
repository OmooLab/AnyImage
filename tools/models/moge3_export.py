# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = [
#   "torch==2.13.0", "torchvision==0.28.0", "onnx==1.22.0", "numpy==2.4.6",
#   "triton-windows==3.7.1.post27; sys_platform == 'win32'",
#   "moge @ git+https://github.com/microsoft/MoGe.git@74fbce054ebed49800de42d0ad0e83495065719a",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch" }
# torchvision = { index = "pytorch" }
# [[tool.uv.index]]
# name = "pytorch"
# url = "https://download.pytorch.org/whl/cu130"
# explicit = true
# ///
"""Export the dynamic MoGe-3 backbone and sparse refinement ONNX graphs."""

import argparse
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
from moge.model.v3 import MoGeModel
from moge.utils.geometry_torch import normalized_view_plane_uv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "anyimage"))
from server.models.onnx_moge3 import build_sparse_inputs


class Moge3Backbone(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, image, num_tokens):
        m = self.model
        aspect = image.shape[-1] / image.shape[-2]
        bh = (num_tokens / aspect).sqrt().round().long()
        bw = (num_tokens * aspect).sqrt().round().long()
        feat, cls = m.encoder(image, bh, bw, return_class_token=True)
        features = []
        for level in range(5):
            uv = normalized_view_plane_uv(
                width=bw * 2**level,
                height=bh * 2**level,
                aspect_ratio=aspect,
                dtype=image.dtype,
                device=image.device,
            ).permute(2, 0, 1)[None]
            features.append(torch.cat([feat, uv], 1) if level == 0 else uv)
        neck = m.neck(features)
        return (
            m.points_head(neck)[-1].permute(0, 2, 3, 1).float(),
            features[0],
            m.normal_head(neck)[-1],
            m.mask_head(neck)[-1],
            m.scale_head(cls),
        )


class Moge3Refiner(torch.nn.Module):
    def __init__(self, r):
        super().__init__()
        self.r = r
        self.n = len(r.down_stages)

    def conv(self, m, x, idx):
        padded = torch.cat([x, torch.zeros_like(x[:1])], 0)
        weights = m.weight.reshape(m.out_channels, 27, m.in_channels).permute(1, 2, 0)
        result = padded[idx[:, 0]] @ weights[0]
        for k in range(1, 27):
            result = result + padded[idx[:, k]] @ weights[k]
        return result + m.bias

    def stage(self, stage, x, idx):
        for b in stage:
            y = F.silu(b.norm1(x))
            y = F.silu(self.conv(b.conv1, y, idx))
            y = self.conv(b.conv2, y, idx)
            x = y + b.skip_connection(x)
        return x

    def forward(self, coord, encoder, *args):
        n = self.n
        ns = args[:n]
        ps = args[n : 2 * n - 1]
        us = args[2 * n - 1 : 3 * n - 2]
        ei = args[-1]
        r = self.r
        x = r.input_proj(coord.reshape(-1, 3))
        skips = []
        for i, stage in enumerate(r.down_stages):
            x = self.stage(stage, x, ns[i])
            if i < n - 1:
                skips.append(x)
                padded = torch.cat([x, torch.zeros_like(x[:1])], 0)
                count = (ps[i] < x.shape[0]).sum(1, keepdim=True).to(x.dtype)
                x = r.downsample_blocks[i].linear(padded[ps[i]].sum(1) / count)
        ef = encoder.permute(0, 2, 3, 1).reshape(-1, encoder.shape[1])[ei]
        x = r.fuse_proj(torch.cat([x, r.encoder_fuse(ef)], -1))
        x = self.stage(r.bottleneck_stage, x, ns[-1])
        for i, (up, stage) in enumerate(zip(r.upsample_blocks, r.up_stages)):
            level = n - 2 - i
            x = up.linear(x)[us[level]] + skips[level]
            x = self.stage(stage, x, ns[level])
        return r.out_proj(x).reshape(coord.shape[0], coord.shape[1], coord.shape[2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--checkpoint", default="Ruicheng/moge-3-vitl")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    checkpoint_options = (
        {"revision": "184008f877d7ad1ad4c2cd2182a9bd1f63d0e5be"}
        if args.checkpoint == "Ruicheng/moge-3-vitl"
        else {}
    )
    model = (
        MoGeModel.from_pretrained(args.checkpoint, **checkpoint_options).eval().cuda()
    )
    model.onnx_compatible_mode = True
    backbone = Moge3Backbone(model).eval()
    image = torch.zeros(1, 3, 192, 256, device="cuda")
    with torch.no_grad():
        coord, encoder, *_ = backbone(image, torch.tensor(64, device="cuda"))
    sparse = build_sparse_inputs(coord.cpu().numpy())
    indices = [torch.from_numpy(value).cuda() for value in sparse.values()]
    names = ["coord", "encoder", *sparse]
    axes = {name: {0: "count_" + name} for name in sparse}
    axes.update(
        coord={1: "height", 2: "width"},
        encoder={2: "token_height", 3: "token_width"},
        delta={1: "height", 2: "width"},
    )
    torch.onnx.export(
        Moge3Refiner(model.refiner).eval(),
        (coord, encoder, *indices),
        str(args.destination / "refiner.onnx"),
        input_names=names,
        output_names=["delta"],
        dynamic_axes=axes,
        opset_version=18,
        dynamo=False,
    )
    torch.onnx.export(
        backbone,
        (image, torch.tensor(1200, device="cuda")),
        str(args.destination / "backbone.onnx"),
        input_names=["image", "num_tokens"],
        output_names=["coord", "encoder", "normal", "mask", "scale"],
        dynamic_axes={
            "image": {2: "height", 3: "width"},
            "coord": {1: "grid_height", 2: "grid_width"},
            "encoder": {2: "token_height", 3: "token_width"},
            "normal": {2: "grid_height", 3: "grid_width"},
            "mask": {2: "grid_height", 3: "grid_width"},
        },
        opset_version=18,
        dynamo=False,
    )


if __name__ == "__main__":
    main()
