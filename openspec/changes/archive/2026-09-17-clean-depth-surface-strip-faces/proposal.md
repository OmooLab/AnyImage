## Why

Depth Plane 与 Depth Cutout 的 Split Edges 会在深度过渡区域产生一张面宽的条带和孤立四边面。拆边后检查四边面的两组对边，可以识别这些结构，同时保留只有相邻两条边为边界的普通表面角落。独立节点组实验已验证该判定及单次删除行为。

## What Changes

- `O Image Depth Plane` 与 `O Image Depth Cutout` 在启用 Split 的分支中，拆边后默认执行一次条带删面。
- 仅选择至少一组对边均为边界边的四边面；边界边的 Face Count 必须等于 1。
- 正式接口不增加实验中的 `Remove Strip Faces` 输入。`Split Threshold = 0` 时旁路拆边和条带删面。
- 两组的 `Split Threshold` 从 `Options` 移到主输入区，紧邻并位于 `Smooth` 前；名称、默认值、范围和阈值映射保持现状。
- 共用节点构建逻辑，并更新针对面数保留、接口顺序和厚度连接的行为测试。

## Capabilities

### New Capabilities

- `depth-surface-strip-cleanup`：拆边后默认进行单次四边面对边界边筛选删面，以及两个节点组的 Split 输入位置。

### Modified Capabilities

无。当前 `openspec/specs/` 为空；本提案依据当前源码及实验结果定义增量行为。

## Impact

涉及 `tools/nodes/common/depth_surface.py`、两个 Depth 节点组构建模块和对应测试。运行时继续加载正式命名的节点资产。实现阶段只修改源码与测试并执行测试；正式 `.blend` 的重建发布另行安排。

三角面及其他非四边面保持原行为。当前 Cutout 建网流程产生三角面，因此本次规则对这类输入不会删面；四边网格输入的实验效果不能作为三角网格的验收结果。条带判定依据拓扑，已被拆成条带的真实物体细节也可能被删除。
