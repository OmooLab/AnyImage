## Why

Depth Surface 的 Stretch Limit 通过删几何处理深度断层，在粗网格上产生斑驳缺面。面深度拆边实验已能保留表面并分离遮挡关系，但增加厚度后侧壁与正面脱开，且目前阈值的操作方向不符合使用习惯。

## What Changes

- **BREAKING**：移除 Depth Surface 及外层 Cutout 的 Stretch Limit 接口、拉伸删几何及其松散拓扑清理分支，以 Options 中的 `Split` 替代。
- 使用“场景 Z 差 / 置换前相邻面中心实际距离”识别需要拆开的共享边。Uniform Scale 使用现有图片标定结果，Depth Scale 参与判断。
- `Split` 范围为 `0–1`，默认 `0` 完全关闭；越大越容易分离。中点 `0.5` 对应实验内部 Split Ratio `5`。
- 拆边后保留面所属侧的采样数据，贯穿原 Depth Surface 投影和厚度流程；修复侧壁与正、背面连接，使有厚度的分离区域具有完整边界。
- Depth Surface 的 Cleanup 放在 Split Edges 之后、投影和厚度之前，按拆分后的平面区域清理小碎片。
- 多个物体共同引用资产中的节点组，通过各自修改器传入图片和标定数据；四种 Shape 继续共享基础网格。
- 整理资产中全部七个几何节点组：主轴横排、支线双侧错落并就近汇入，必要的回接直接连接，验证 Repeat 区域的排列；将布局经验写入 AGENTS.md。

## Capabilities

### New Capabilities

- `depth-surface-face-separation`：规定分离控制、面深度判据、厚度连接完整性和共享节点集成行为。

### Modified Capabilities

无。当前 `openspec/specs` 尚无对应主规格；本变更替代已实现的 `restore-depth-surface-stretch-culling` 的产品行为，不改写其历史记录。

## Impact

- `tools/node_assets/build_cutout.py`、节点验证及 `src/anyimage/assets/O_AnyImage.blend`。
- Cutout 真实 Blender 求值测试、接口结构测试及节点资产说明。
- 原 Depth Surface 的厚度生成与采样属性传递需要联合验证，并回归外层 Cleanup、Smooth 和其他 Shape。
- 复用现有 Depth Image、Uniform Scale 和 Reference Depth 输入；不新增模型推理或依赖。
