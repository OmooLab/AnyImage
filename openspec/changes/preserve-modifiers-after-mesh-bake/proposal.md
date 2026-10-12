## Why

Bake Mesh 当前要求整个修改器栈精确匹配 AnyImage 节点组，用户在 Cutout 后添加 Smooth 或自定义 Geometry Nodes 后便无法烘焙。将烘焙范围限定为栈开头的 AnyImage 生成部分，可以固化基础模型并继续使用后续修改器。

## What Changes

- 统一识别修改器栈开头的 AnyImage 烘焙部分，菜单可用性和执行使用同一边界。
- Cutout 支持 `O Image Cutout`、`O Image Depth Cutout`，以及 `O Image Depth Cutout → O Image Cutout Symmetry`；单区图片转换沿用当前支持的节点组。
- 允许该部分之后存在任意修改器或 Geometry Nodes，烘焙仅对 AnyImage 部分求值。
- 成功后只移除已烘焙修改器，保留后续修改器实例、顺序、参数和启用状态；失败恢复临时状态及已有数据事务。
- 沿用静态贴图、共享数据隔离、对象能力退出及 Undo/Redo 行为。

## Capabilities

### New Capabilities

- `mesh-bake-modifier-prefix`: 定义 AnyImage 修改器前缀的识别、隔离求值、后续修改器保留和失败恢复。

### Modified Capabilities

## Impact

- `src/anyimage/operators/bake_mesh/` 的可用性判断、网格求值和成功提交。
- `tests/anyimage/operators/test_mesh_materialization.py`、`test_single_region_materialization.py` 及相关菜单测试。
- 与现有 `refine-image-workflow-boundaries` 的 Bake 校验和事务要求共同生效。
