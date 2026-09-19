## Why

使用 inverse 类颜色空间时，用户观察到 Alpha 无法正确遮盖图片边缘，手动添加 Float Curve 后可改善。将这项调整放入 O Image Layer，让材质创建时自动应用，并允许用户调节强度。

## What Changes

- O Image Layer 内新增 Alpha Float Curve，依据参考图设置曲线。
- 默认折叠的 `Options` 面板依次包含 `Alpha Fix`、`Normal Scale`、`Object Space`；Alpha Fix 连接 Float Curve 的 Factor，范围 0–1，默认 0。
- 创建使用 O Image Layer 的材质时，读取 `Adapt to Scene View Transform`：开启设为 1，关闭设为 0。
- 验证曲线、接口、材质创建和着色输出行为。

## Capabilities

### New Capabilities

- `image-layer-alpha-adjustment`: 材质层 Alpha 曲线调整、强度输入与创建时偏好联动。

### Modified Capabilities

无。

## Impact

- `tools/node_assets/material_layers.py`：节点组接口、曲线与布局。
- `src/anyimage/common/material.py`：创建节点实例时设置调整强度。
- `tools/node_assets/asset_validation.py` 及材质相关测试：接口、连接、曲线求值和偏好联动验证。
- 发布节点资产 `src/anyimage/assets/O_AnyImage.blend` 需要包含新接口；本轮仅生成提案。
