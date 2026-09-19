## Why

Depth Cutout 的 Split 新边界仍继承原 Balloon 厚度，容易膨胀成尖脊；Boundary Smooth 在锯齿三角形上可能翻面，进一步改变厚度方向。恐龙头骨实图实验已确认边界厚度收敛、切口圆润和薄厚度下减弱法向平滑的效果，需要将这些行为整理为正式节点实现。

## What Changes

- Split 后清理三个顶点都位于边界的三角面，降低锯齿切口的退化风险。
- 新切口的 Balloon 厚度在边界收敛为零，邻近区域逐渐恢复；Edge Round 同时控制新切口的圆润过渡。
- 法向平滑结果按厚度连续混合：薄厚度接近原法向，正常厚度恢复既有平滑效果，默认始终启用。
- 保留 Split Threshold、Boundary Smooth 及厚度、Edge Round 的实时调节，参数变化后重新计算边界与形状。

## Capabilities

### New Capabilities

- `cutout-split-boundary-shaping`：切口清理、边界厚度收敛、圆润过渡及厚度关联法向平滑。

### Modified Capabilities

## Impact

- `tools/nodes/groups/image_depth_cutout.py` 及必要的 `tools/nodes/common` 构建函数。
- `tests/tools/nodes` 的 Cutout、边界平滑及属性生命周期测试。
- `src/anyimage/assets/O_AnyImage.blend` 中的 Cutout 节点资产及对应加载版本。
- 基于当前工作区的边界深度平滑继续实施，保留已有修改。
