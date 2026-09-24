## Why

Depth Cutout 当前通过 Faces Extrude 同时生成背面和侧壁；背面轮廓沿面域位移后仍有明显锯齿，而在已闭合网格上无法再获得开放边界的 pinned smoothing 效果。前次试作把不同生成顺序的几何误当成共同平滑的对照，并混用了动态 Index，导致错误归因。需要固定同源叶片、共同平滑和稳定桥接协议。

## What Changes

- 将正面和背面构造成同源、拓扑不变的两个开放叶片；背面位移先显式求值到 Face domain，并在进入后续阶段前翻面。
- Front 与已完成 Face-domain 位移、Rear Smooth、Flip Faces 的 Rear 先 Join，再以一个 Repeat Zone 共同执行 Boundary Smooth；零厚度时同一路径只输入 Front。
- 在最终单层 projection topology 上计算并保存 Outline、Split 与 Depth Limit 的完整平滑权重；raw cut marker 仅维持字段惰性依赖，不作为共同 Repeat 的直接输入，并在最终输出统一清理。
- 仅提取正面边界边，以 Edges Extrude 将每个边界点连接到背面同源点；不再用 Faces Extrude 的面域 Offset 模拟逐点桥接。
- 用拓扑阶段内保存的 source index 建立对应关系；禁止依赖 Join、Separate Geometry 或 Sort Elements 后临时 `Index` 的偶然顺序。
- 保留 Rear Smooth、Balloon / Shell、Depth Split、Depth Limit、UV 与属性语义；正厚度结果保持闭合、有限且无交叉侧壁。
- 以分阶段几何检查和行为测试覆盖叶片生成、共同平滑、索引对应、侧壁朝向及最终焊接；共同与独立平滑的等价比较必须使用完全相同的未平滑叶片输入。

## Capabilities

### New Capabilities

- `depth-cutout-leaf-bridging`: 定义同源前后叶片、稳定边界点对应、边界边 Extrude 侧壁及闭合方向协议。

### Modified Capabilities

- `cutout-boundary-smoothing`: Boundary Smooth 在同源的前后断开叶片上共同执行，保持既有 Split / Outline 权重、pin 行为和单叶片效果。
- `cutout-geometry-node-efficiency`: 正厚度 Depth Cutout 使用单个 Boundary Smooth Repeat Zone，并约束额外索引与桥接工作为线性复杂度。

## Impact

影响 `nodes/groups/image_depth_cutout.py`、必要的 `nodes/common/` 共用字段函数、节点布局规则、Depth Cutout 行为测试和生成的 `src/anyimage/assets/O_AnyImage.blend`。公开节点接口、依赖和运行时 Python API 不变。
