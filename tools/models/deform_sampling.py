"""Express BiRefNet's single-group deformable convolution with GridSample."""

import torch
from torch.nn import functional as F


def deform_conv(input, offset, weight, bias=None, stride=(1, 1), padding=0, mask=None):
    batch, channels, height, width = map(int, input.shape)
    output_height, output_width = map(int, offset.shape[-2:])
    kernel_height, kernel_width = map(int, weight.shape[-2:])
    count = kernel_height * kernel_width
    y, x = torch.meshgrid(
        torch.arange(output_height, dtype=input.dtype, device=input.device),
        torch.arange(output_width, dtype=input.dtype, device=input.device), indexing="ij",
    )
    ky, kx = torch.meshgrid(
        torch.arange(kernel_height, dtype=input.dtype, device=input.device),
        torch.arange(kernel_width, dtype=input.dtype, device=input.device), indexing="ij",
    )
    offsets = offset.reshape(batch, count, 2, output_height, output_width)
    sy = y[None, None] * stride[0] - padding + ky.reshape(1, count, 1, 1) + offsets[:, :, 0]
    sx = x[None, None] * stride[1] - padding + kx.reshape(1, count, 1, 1) + offsets[:, :, 1]
    coordinates = torch.stack((sx * (2.0 / (width - 1)) - 1, sy * (2.0 / (height - 1)) - 1), -1)
    grid = coordinates.permute(0, 2, 3, 1, 4).reshape(batch, output_height, output_width * count, 2)
    sampled = F.grid_sample(input, grid, mode="bilinear", padding_mode="zeros", align_corners=True)
    sampled = sampled.reshape(batch, channels, output_height, output_width, count).permute(0, 1, 4, 2, 3)
    sampled = (sampled * mask[:, None]).reshape(batch, channels * count, output_height, output_width)
    return F.conv2d(sampled, weight.reshape(int(weight.shape[0]), channels * count, 1, 1), bias)


def validate_deform():
    from torchvision.ops import deform_conv2d

    torch.manual_seed(12)
    for kernel in (1, 3, 7):
        image = torch.randn(1, 4, 17, 19)
        offset = torch.randn(1, kernel * kernel * 2, 17, 19) * 3
        mask = torch.rand(1, kernel * kernel, 17, 19) * 2
        weights = torch.randn(5, 4, kernel, kernel)
        bias = torch.randn(5)
        reference = deform_conv2d(image, offset, weights, bias, padding=kernel // 2, mask=mask)
        actual = deform_conv(image, offset, weights, bias, padding=kernel // 2, mask=mask)
        torch.testing.assert_close(actual, reference, atol=1e-4, rtol=1e-4)


if __name__ == "__main__":
    validate_deform()
