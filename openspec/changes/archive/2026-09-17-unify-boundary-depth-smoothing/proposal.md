## Why

Alpha 轮廓和有效性剔除留下的网格边界仍可能采到突变深度，形成尖刺。独立 Blender 实验已验证：在置换前平滑边界采样深度，再执行现有边界网格平滑，可明显改善 Depth Cutout，并进一步改善 Depth Plane。

## What Changes

- 为 `O Image Depth Cutout`、`O Image Depth Plane`、`O Image Depth Panorama` 统一加入置换前的边界深度平滑。
- 复用 `Boundary Smooth` 控制深度 Blur 与现有边界网格平滑的迭代数，保留默认值 `5`、范围 `0–20`；`0` 完全关闭两者。
- 在有效性剔除及 Split 后的连通网格上平滑深度标量，仅应用于可处理边界及邻近两圈，并保持各顶点原投影方向。
- Cutout 的原 Alpha 轮廓参与分批自适应深度平滑，Outline Depth Fix 控制批次数、Boundary Smooth 控制每批步数，Ratio 固定 0.25–0.5，保护 Split 切边；Depth Plane 保留原矩形外框保护；Panorama 按球面径向距离处理实际网格边界。
- 复用公共构建函数，补齐行为测试、全景专项验证与节点资产重建。

## Capabilities

### New Capabilities

- `boundary-depth-smoothing`：三个深度表面的统一参数、边界选择、采样阶段、投影保持及资产验证。

### Modified Capabilities

## Impact

- `tools/nodes/common/boundary_smoothing.py` 及三个深度表面节点构建模块。
- `tests/tools/nodes` 中的边界平滑、深度表面、Cutout 和全景行为测试。
- `src/anyimage/assets/O_AnyImage.blend` 中对应节点组及必要的资产版本标识。
- Cutout、Depth Plane 和 Panorama 的资产读取入口：新建对象请求本次节点版本，保留场景内旧组的现有使用者。
- 使用现有 Blender 节点与依赖；深度平滑在几何节点求值阶段完成。
