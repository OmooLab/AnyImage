## Why

`O Image Cutout` 和 `O Image Depth Cutout` 是 Cutout 的主成形节点组。Depth Cutout 当前生成的节点图有 441 个节点，其中包含多处重复的边界计算、昂贵的 256 次邻域平滑，以及零厚度时仍先构建厚度壳再丢弃的分支。这些冗余不会改变现有结果，但会显著影响高密度 Cutout 网格的求值速度和节点可读性。

## What Changes

- 保持 `O Image Cutout` 与 `O Image Depth Cutout` 的公开输入、输出几何和现有视觉行为不变。
- 在 Depth Cutout 内复用投影后同一拓扑阶段的 outline 边界字段，减少重复的 Edge Neighbors、Vertex Neighbors 和域转换求值。
- 用 `depth_slow - profile_slow` 推导中心场，消除一次重复的 256 次邻域平滑。
- 将 Depth Cutout 的 strip 清理改为仅构建三角形路径；Depth Cutout 输入已确认为三角面。
- 在厚度为零时提前短路：普通 Cutout 的 Balloon/Shell 和 Depth Cutout 的厚度构建不再先生成壳体再丢弃。
- 整理几何节点临时属性命名：仅内部使用并在输出前清理的属性使用 `_o_` 前缀；需要保留为公开协议的属性使用 `o_` 前缀。
- 输出前使用一个 `Remove Named Attribute` 的 Wildcard 模式清理全部内部临时属性，不再逐项删除。
- 更新相关节点构建测试、属性清理测试和高密度网格回归测试，并重建 `O_AnyImage.blend`。

## Capabilities

### New Capabilities

- `cutout-geometry-node-efficiency`: 规定两个 Cutout 节点组在不改变输出几何的前提下复用共享字段、短路零厚度分支，并按三角输入构建专用清理路径。
- `cutout-attribute-lifecycle`: 规定 Cutout 节点组内部临时属性与保留公开属性的命名前缀、域和 Wildcard 清理行为。

### Modified Capabilities

无。当前 `openspec/specs` 尚未建立对应主规格；本变更不修改既有用户能力的需求。

## Impact

- `tools/nodes/groups/image_cutout.py`
- `tools/nodes/groups/image_depth_cutout.py`
- `tools/nodes/common/depth_surface.py`
- `tools/nodes/common/cutout_boundary.py`
- `tools/nodes/common/boundary_smoothing.py`
- `tools/nodes/common/cutout.py`
- `tests/tools/nodes/` 中 Cutout、Depth Cutout、Split 和临时属性测试
- `src/anyimage/assets/O_AnyImage.blend`

