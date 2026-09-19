## 1. Boundary behavior

- [x] 1.1 区分 Depth Cutout 的 Split 与 Outline influence，并在单一平滑循环中应用完整与 0.1 倍权重。
- [x] 1.2 将 O Image Depth Cutout 的 Boundary Smooth 默认值改为 4，保持零值旁路和既有范围。

## 2. Verification and asset

- [x] 2.1 更新相关行为与接口测试，覆盖 Split 优先、Outline 弱权重、默认值和关闭行为。
- [x] 2.2 运行相关测试，执行 `uv run node-group build` 并确认保存资产验证通过。
