## Why

Depth Cutout 原有单段 Edges Extrude 能形成清晰、稳定的前后转折，但侧面 UV 面积过窄会把纹理沿厚度明显拉伸；改成前后边界直接收拢到中值后虽消除了侧面 UV，却会在接缝形成尖峰。需要保留 Extrude 桥接几何，并让叶片边缘带分担少量过渡，同时避免采样透明轮廓之外。

## What Changes

- 保留同源、共同平滑的 Front / Rear leaf，不再移动两张 leaf 的边界或邻近点。
- 按 source index 计算对应边界点的共享 Side ring；`Side Roundness` 在平直中值与最多外移四分之一局部厚度的法线约束目标之间调节，默认 `0.5`，Front 与 Rear 分别向该环执行半段 Edges Extrude 并焊接。
- 以四次局部 UV Blur 得到内侧方向；Side 中间环保持 original UV，不向透明轮廓之外扩展。
- Front / Rear 边缘 UV 沿内侧方向移动 `0.5`，并向内四圈渐变到零；该位移随实际厚度在 `0～1` 平滑启用，并以 `Pow 0.5` 提前增强低厚度响应，Side base 继承调整后的 leaf boundary UV。
- Front 的 Normal Reduction 从零厚度语义平滑过渡到既有 balloon profile，避免 Thickness 从零变为正数时边缘法线突变。
- Bridge UV 直接将 Corner UV 一次转换到 Point domain，避免逐分量重复转换。
- Boundary Smooth 与 Top UV 共用一次计算的四圈 `_o_boundary_falloff`；几何平滑继续叠加独立的 cut/outline 程度。
- Front 与 Rear 原 faces 和 positions 保持不变；仅边缘四圈 Corner UV 参与过渡，并允许中间环保留 UV seam。
- 保留 Rear Smooth、共同 Boundary Smooth、Depth Split、Depth Limit、Balloon / Uniform 与零厚度旁路语义。
- 增加双向 Extrude、中间环对应、Side UV、叶片边缘 UV 渐变及多边界闭合测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `depth-cutout-leaf-bridging`: 将中值收口改为 Front / Rear 双向半段 Extrude，并定义 leaf 边缘内移、Side UV 与厚度渐变协议。
- `cutout-geometry-node-efficiency`: 约束双向 Extrude、source-index lookup、UV 字段与最终焊接保持线性复杂度。

## Impact

影响 `nodes/groups/image_depth_cutout.py`、必要的 `nodes/common/` 共用字段函数、Depth Cutout 节点布局与行为测试，以及重新生成的 `src/anyimage/assets/O_AnyImage.blend`。公开节点接口新增 `Side Roundness`，材质、运行时 Python API 和依赖不变。
