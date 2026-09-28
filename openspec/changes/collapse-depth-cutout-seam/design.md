## Context

Depth Cutout 已从同一投影拓扑生成 Front 与 pre-flipped Rear，以 source index 保持点对应，并在桥接前共同执行 Boundary Smooth。单段 Front-to-Rear Edges Extrude 的几何转折符合预期，但 Side faces 沿厚度方向展开了过多图像内容。后续中值收口试作删除了 Side faces，却使两张 leaf 在共同边界形成尖峰。

二维图像没有真实侧面信息，无法同时获得完整侧面细节和零拉伸。实图调节确认：Side UV 向轮廓外扩展会在透明边界产生完全透明的 Side，因此中间环必须保持 original UV；四次 UV Blur 后让叶片边缘向内移动少量，可以在不越过图像轮廓的前提下缓解拉伸。

## Goals / Non-Goals

**Goals:**

- Front / Rear leaf 的位置与面不因桥接改变，Corner UV 只在边缘四圈渐变调整。
- Front 与 Rear 各生成半段 Side，并在 source-index 对应的共享目标形成共同中间环。
- 每半段 Side 的 UV 从调整后的 boundary UV 过渡到 original boundary UV，降低实体侧面与 UV 面积的拉伸比且不采样轮廓外部。
- Thickness 从零增大时，leaf UV pull 与 Front Normal Reduction 连续渐入。
- 正厚度输出保持闭合、定向一致、有限且无退化面。
- 保留 source index、共同 Boundary Smooth、Rear Smooth 与零厚度旁路。

**Non-Goals:**

- 不新增公开 UV 控制或独立 Side Material。
- 不生成真实侧面纹理，也不改写材质节点。
- 不改变投影、厚度、Depth Split 或 Depth Limit 算法。
- 不使用 Capture Attribute、Mesh Boolean 或扩大 Merge by Distance 容差。

## Decisions

### 1. 双向半段 Extrude 使用可调共享 Side ring

共同 Boundary Smooth 完成并分离 leaf 后，按 `_o_leaf_source_index` 查找对应位置。`Side Roundness = 0` 时共享目标为 `M = (Front + Rear) / 2`。正值使用 Front normal 与反向 Rear normal 的角平分方向定义局部切平面，将 `Blur(Position) - Position` 投影到该平面并取反得到轮廓外侧方向 `O`，再计算 `M' = M + O × distance(Front, Rear) × 0.25 × Side Roundness`。Front 计算并存储唯一目标，Rear 按 source index 采样同一目标，保证两侧精确焊接。

`Side Roundness = 0` 保持 `Front → M → Rear` 共线；`1` 使用受法线约束且最多外移四分之一局部厚度的稳定极值，使两个 Side faces 形成浅凸折角。默认 `0.5` 等价于实测旧范围的 `0.25`。字面切线交点在平行 Front / Rear 上位于无穷远，因此不作为可用极值。Front / Rear leaf 本身不移动，面数不随 Roundness 改变。

### 2. Leaf 边缘内移，Side 中间环保持 original UV

每张 leaf 在 Extrude 前将 Corner-domain `UVMap` 求值到 Point domain，并执行四次局部 Blur。定义 `D = blurred_uv - original_uv`，其中 D 指向 UV 岛内部。

以当前模式实际最大位移计算 `thickness_strength = pow(smoothstep(0, 1, max_displacement), 0.5)`，让低于 1 的厚度更早接近完整效果。Leaf UV 使用 `original_uv + D × 0.5 × boundary_falloff × thickness_strength`，falloff 在边界为 1，向内四圈渐变到 0。Side base corners 继承调整后的 leaf boundary UV；Side top corners 保持 original UV。固定比例不新增公开输入。

Corner-domain `UVMap` 直接通过一个 FLOAT_VECTOR Field on Domain 转为 Point domain，不再拆分 U/V 后分别转换；该精简保持逐分量平均结果等价，不改变 Boundary Smooth 或 Blur 次数。

投影网格在 Front / Rear 分离前计算一次四圈 `_o_boundary_falloff`。Top UV 直接使用完整 falloff；Boundary Smooth 使用相同 falloff 作为范围，并将 Depth Split / Depth Limit cut influence 设为完整程度、原始 Outline 设为 `0.1`。`_o_boundary_smooth_weight` 仍只保存几何平滑的最终程度。

Leaf UV 只写入边缘影响带，带外 Corner UV 不变；Side UV 只写入提取后的 Side faces。中间环的几何点焊接后，两半 Side 仍可在 Corner domain 保留各自 UV；这是允许且预期的 UV seam。

### 3. 两半 Side 独立构建后统一精确焊接

每次 Edges Extrude 都接收完整 leaf 和其 Mesh Boundary selection，以保留输入面绕向。Top 仅由 source-index Side ring target attribute 重定位，最终只保留 Side faces。Front、Rear、Front Side 与 Rear Side Join 后使用固定 `1e-6` ALL Merge by Distance，合并 leaf/side 基座及共同中间环。

Merge 只焊接已对应的位置，不承担配对。所有删除、复制或拓扑改变仍须发生在 source index 建立之前。

### 4. 零厚度继续旁路整个桥接分支

正厚度分支才求值 Rear、Side ring target、UV pull、两次 Extrude 与最终 Merge。零厚度仍输出共同 Boundary Smooth 后的单层 Front。

### 5. Front Normal Reduction 随厚度渐入

Front 的 material normal strength 使用 `mix(1, balloon_profile, thickness_strength)`；Shell 的目标值仍为 1。零厚度附近保持原 Front normal，实际最大位移达到 `1` 后恢复既有 balloon profile。Rear 与 Side 继续写入完整 Normal Reduction。

Boundary Smooth 与 bridge UV Blur 保持独立：前者继续在 pinned smooth 中同步调整位置与 UV，后者只为 Side 过渡计算内侧 UV 方向，本次不合并或复用两者。

## Risks / Trade-offs

- **透明轮廓使 Side 消失** → Side top 固定使用 original boundary UV，不再向轮廓外扩展。
- **Leaf 边缘 UV 变形可见** → 最多移动 `0.5`，通过四圈 falloff 与厚度强度平滑归零。
- **Thickness 从零变化时属性突变** → UV pull 与 Front Normal Reduction 共用基于实际位移的 Smoothstep 强度。
- **中间环出现可见 UV seam** → 两半 Side 分别来源于 Front / Rear，Corner seam 不影响几何闭合；同源叶片通常得到相近 UV。
- **Rear Side 绕向错误** → Rear 先 Flip Faces，并用有向边使用次数验证最终闭合方向。
- **双向 Extrude 增加一圈 faces** → face 数仍只随边界边数线性增长，不增加 Repeat Zone 或 nearest 查询。
- **Merge 误焊窄缝** → 保持固定 `1e-6`，中间点通过 source index 明确计算。
- **Roundness 在窄洞或凹角自交** → 极值限制为局部 Front / Rear 距离的四分之一，默认值为 `0.5`。

## Migration Plan

1. 删除中值收拢与两圈 seam influence 节点。
2. 保留 Front / Rear source-index lookup，计算可调的共享 Side ring target。
3. 为每张 leaf 计算四次 Blur、边缘 falloff 与厚度渐变，分别构建到中间环的 Edges Extrude Side。
4. Join leaves 与两半 Side，以固定容差焊接。
5. 更新测试，运行相关测试及 `uv run --group blender node-group build`。

回滚时可恢复上一版中值收口节点链；公开接口和存量对象无需迁移。

## Open Questions

无。
