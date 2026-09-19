## Why

验证 MoGe 多视图距离融合与 Blender 几何节点能否组成全景表面生成流程，为后续产品方案提供实测依据。

## What Changes

- 在 `experiments/panorama_surface` 实现独立试验，使用可计算真实距离的合成全景验证投影、融合与网格。
- 使用本地 MoGe2 ONNX 模型完成一次多视图推理，输出距离图和独立 Blender 示例。
- 检查可调细分 Quad Sphere、全景 UV、Mask 与 Alpha 剔除及 Blender 重新加载后的求值。

## Capabilities

### New Capabilities

- `panorama-surface-prototype`: 独立的全景距离融合和几何节点验证。

### Modified Capabilities

## Impact

新增试验目录和本提案目录。试验复用当前 Python、NumPy、SciPy、ONNX Runtime 与 Blender 环境，生产源码、依赖及原节点资产保持原状。
