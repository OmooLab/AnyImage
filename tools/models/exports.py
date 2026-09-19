"""Export official PyTorch super-resolution models to ONNX."""

import numpy as np


OPSET_VERSION = 17


def _require_build_dependencies():
    try:
        import onnx
        import onnxruntime
        import torch
    except ImportError as error:
        raise RuntimeError(
            "Model build dependencies are missing. Run with: "
            "uv sync --group models"
        ) from error
    return onnx, onnxruntime, torch


def _load_weights(torch, checkpoint_path, key):
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    return checkpoint[key]


def _validate_export(onnx, onnxruntime, torch, model, sample, destination):
    onnx.checker.check_model(onnx.load(destination))
    expected = model(sample).detach().numpy()
    session = onnxruntime.InferenceSession(
        str(destination),
        providers=["CPUExecutionProvider"],
    )
    actual = session.run(None, {"input": sample.numpy()})[0]
    np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-5)


def _export(torch, model, sample, destination, dynamic_axes=None):
    model.eval()
    torch.onnx.export(
        model,
        sample,
        destination,
        export_params=True,
        opset_version=OPSET_VERSION,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
        dynamo=False,
    )


def _restore_realesrgan_scope_names(onnx, destination):
    model = onnx.load(destination)
    for node in model.graph.node:
        node.name = node.name.replace("/body.", "/body/body.")
        for values in (node.input, node.output):
            for index, value in enumerate(values):
                values[index] = value.replace("/body.", "/body/body.")
    onnx.save(model, destination)


def export_realesrgan_wdn_x4(checkpoint_path, destination):
    onnx, onnxruntime, torch = _require_build_dependencies()
    nn = torch.nn

    class SRVGGNetCompact(nn.Module):
        def __init__(self):
            super().__init__()
            self.upscale = 4
            self.body = nn.ModuleList([nn.Conv2d(3, 64, 3, 1, 1), nn.PReLU(64)])
            for _ in range(32):
                self.body.extend([nn.Conv2d(64, 64, 3, 1, 1), nn.PReLU(64)])
            self.body.append(nn.Conv2d(64, 3 * self.upscale**2, 3, 1, 1))
            self.upsampler = nn.PixelShuffle(self.upscale)

        def forward(self, value):
            result = value
            for layer in self.body:
                result = layer(result)
            result = self.upsampler(result)
            return result + torch.nn.functional.interpolate(
                value,
                scale_factor=self.upscale,
                mode="nearest",
            )

    model = SRVGGNetCompact()
    model.load_state_dict(_load_weights(torch, checkpoint_path, "params"), strict=True)
    sample = torch.rand(1, 3, 16, 16)
    dynamic_axes = {
        "input": {2: "height", 3: "width"},
        "output": {2: "height4", 3: "width4"},
    }
    _export(torch, model, sample, destination, dynamic_axes)
    _restore_realesrgan_scope_names(onnx, destination)
    _validate_export(onnx, onnxruntime, torch, model, sample, destination)


def export_model(exporter, checkpoint_path, destination):
    exporters = {
        "realesrgan_wdn_x4": export_realesrgan_wdn_x4,
    }
    try:
        export = exporters[exporter]
    except KeyError as error:
        raise ValueError(f"Unknown model exporter: {exporter}") from error
    export(checkpoint_path, destination)
