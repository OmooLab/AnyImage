## Why

Cutout 用 Alpha 0.1 保留毛发时，边缘可能读取背景深度，形成严重后缩和长条拉伸。猫与人物的实图实验已验证：从可靠内部外延深度，可以保留原 Alpha 轮廓并明显减少拖尾。

## What Changes

- 为 Cutout 的 Depth Surface 与 Depth Balloon 增加导出前的边缘深度修复。
- 以 Alpha ≥ 0.95 且模型深度有效的内部区域为依据，内缩 2 个深度图像素后向边缘外延，并仅对补齐区域轻微平滑。
- 保留颜色 Alpha、0.1 裁切阈值和可靠内部深度；按当前像素的相机射线重建 XYZ。
- 为细小分量、无可靠深度和透明区采样增加确定的处理规则，并补充自动测试与 Blender 实图验收。

## Capabilities

### New Capabilities

- `cutout-edge-depth`: Cutout 的可靠深度区域、边缘外延、投影保持和产物一致性。

### Modified Capabilities

## Impact

- `server/geometry/`：增加深度修复模块，接入推理产物编排。
- `server/jobs/cutout.py`：为 Cutout 深度产物启用修复。
- `runtime.py`、`pyproject.toml`、`uv.lock`：加入 SciPy，复用距离变换与局部滤波，并检查环境及打包测试。
- 服务端几何与任务测试，以及现有 Blender Cutout 修改器的实图验证。
