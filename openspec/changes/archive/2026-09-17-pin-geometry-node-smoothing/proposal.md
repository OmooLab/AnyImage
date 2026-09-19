## Why

`O_AnyImage` 的几何平滑目前只在深度三组里隐式地按边界条带处理边界点，没有任何锐边保护；`O Image Cutout Symmetry` 的 Seam 平滑还会把轮廓往里拖。OmooNodes 的 `O Smooth` 已经证明 `Pin Sharp` 与 `Pin Boundary` 能在保留必要细节的同时得到更干净的表面，本变更把这两层 pin 作为固定为 1 的内部行为引入 `O_AnyImage` 真正位于网格边界的平滑。

## What Changes

- 位于网格边界的顶点位置平滑（`Seam Smooth` 与三个深度节点组的 `Boundary Smooth`）固定开启 `Pin Sharp = 1` 与 `Pin Boundary = 1`，在共享实现内部硬编码，不新增也不修改 modifier 接口。
- `Pin Boundary`：边界点不再取内部模糊结果，改用边界条带自身的 0.5 权重一步模糊；轮廓只沿自身松弛，不被内部平滑拖拽或收缩，边界顶点本身仍会移动。
- `Pin Sharp`：每点平滑权重乘上法线相干度 `|Blur(Normal, 10)|`，尖锐处少动。
- **BREAKING**：`Seam Smooth` 与 `Boundary Smooth` 不再移动或收缩轮廓本身，轮廓改为按 `Pin Boundary` 规则处理。
- `Fill Smooth` 改为衔接带平滑：锚点是 front 的完整边界带（外侧轮廓与对称面上的切缝），范围从两圈扩大到四圈，因此对称轴上的点同样参与；衔接处不是网格边界，因此不做 `Pin Boundary`，保留 `Pin Sharp`。
- 作用范围语义保持不变：`Boundary Smooth`、`Fill Smooth`、`Seam Smooth` 仍是带渐变的区域，范围外顶点不动；Cutout 中原始轮廓与 Split 切边的权重差异（0.1 / 1.0）保留。
- 抽出共享的平滑构建函数，pin 形态与普通形态共用同一个迭代循环，各站点只提供作用范围、权重与是否 pin。
- 属性平滑（Normal Smooth、深度模糊、掩码与统计模糊）不纳入 pin，保持现有实现。

## Capabilities

### New Capabilities

- `pinned-geometry-smoothing`: 规定 `O_AnyImage` 的边界平滑固定开启 Pin Sharp 与 Pin Boundary、衔接带平滑使用普通平滑，并界定作用范围层与 pin 层的职责。

### Modified Capabilities

无。

## Impact

- `tools/nodes/common/smoothing.py`：共享 pinned 平滑实现与边界字段。
- `tools/nodes/common/boundary_smoothing.py`：深度三组的顶点平滑改走共享实现。
- `tools/nodes/groups/image_cutout_symmetry.py`：Fill/Seam 改走共享实现，删除旧的平面内偏移路径。
- `tools/nodes/groups/image_depth_plane.py`、`image_depth_cutout.py`、`image_depth_panorama.py`：调用点收敛到共享实现。
- `src/anyimage/assets/O_AnyImage.blend` 与 `tests/tools/nodes` 下相关测试。
- 公开 modifier 接口不变，不涉及依赖与打包。
