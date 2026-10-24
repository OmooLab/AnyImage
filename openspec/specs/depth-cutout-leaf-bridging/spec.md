# depth-cutout-leaf-bridging Specification

## Purpose
TBD - created by archiving change bridge-smoothed-depth-cutout-leaves. Update Purpose after archive.
## Requirements

### Requirement: Front 与 Rear 使用同源叶片拓扑
`O Image Depth Cutout` SHALL 从投影后的同一最终拓扑构造 Front leaf 与 Rear leaf，只允许改变点位置、属性和面朝向。Rear 位移 SHALL 在 Face domain 求值后应用，并 SHALL 在共同 Boundary Smooth 之前完成 Rear Smooth 与 Flip Faces。Rear Smooth 的 profile strength SHALL 使用 `pow(o_balloon, 0.5)`。

#### Scenario: Face-domain Rear 位移
- **WHEN** 输入面内各点的厚度方向不同且 Thickness 为正
- **THEN** Rear 点位置 SHALL 等于 Face-domain 位移适配到点后的结果
- **AND** 不得以 Point-domain 直接位移替代该结果

#### Scenario: Front 与 Rear 面朝向相反
- **WHEN** 仅输出组合前的 Front 与 Rear
- **THEN** 两张 leaf 的对应面 SHALL 具有相反绕向
- **AND** Rear 不得依赖最终材质双面显示掩盖错误方向

### Requirement: Source index 稳定标识对应点
系统 SHALL 在 Front / Rear 分支之前为最终投影拓扑的每个点保存唯一 source index。Join、Flip Faces、Set Position、Boundary Smooth 与 Separate Geometry SHALL 保留该标识；桥接目标 MUST 按保存的标识查找，不能直接假设当前动态 `Index` 相等。

#### Scenario: Join 与 Separate 后仍能对应
- **WHEN** Front 与 Rear 经 Join、共同平滑并再次拆开
- **THEN** 每个 Front boundary point SHALL 找到 source index 相同的唯一 Rear point
- **AND** 对应线段不得连接到其他 source index

#### Scenario: 对应关系独立于元素排序
- **WHEN** Join 或 Separate Geometry 改变任一 leaf 的当前点序
- **THEN** bridge lookup SHALL 仍返回 source index 相同的 Rear Position
- **AND** Sort Elements 不得用于掩盖缺失、重复或越界的 source index

### Requirement: Wall 仅由对应边界边生成
系统 SHALL 从最终 Front 与 Rear leaf 的全部 Mesh Boundary Edges 分别生成半段 Wall，并按稳定 source index 把两侧 Top points 放到唯一共享 Side ring target。`Side Roundness = 0` 时 target SHALL 是对应 Front / Rear positions 的中值；`1` 时 SHALL 沿法线约束的轮廓外侧方向最多偏移局部厚度的四分之一，默认值 SHALL 为 `0.5`。Front 与 Rear leaf 的原 positions MUST 保持不变。实现 MUST NOT 使用 Faces Extrude 或假设 Join / Separate 后的动态 Index 对应。

#### Scenario: 不对称叶片双向桥接
- **WHEN** Front 与 Rear 是拓扑相同但各点位移不同的不对称非共面网格
- **THEN** Front Side 与 Rear Side 的 Top points SHALL 精确落在同一个 source-index target
- **AND** 两半 Side SHALL 在该中间环焊接，不得连接其他 source index
- **AND** Front / Rear boundary points SHALL 保持桥接前位置

#### Scenario: Side Roundness 调节折角
- **WHEN** `Side Roundness` 从 0 调节到 1
- **THEN** 共享 Side ring SHALL 从 Front / Rear 中值连续移动到法线约束的稳定外移目标
- **AND** `Side Roundness = 1` 的偏移量 SHALL 不超过同源 Front / Rear 距离的四分之一
- **AND** face 数与 source-index 对应 SHALL 保持不变

#### Scenario: 所有开放边界独立闭合
- **WHEN** 网格同时含原始 Outline、洞、Depth Split 与 Depth Limit 形成的开放边界
- **THEN** 每条 Front boundary edge 与对应 Rear boundary edge SHALL 各生成一个半段 Side face
- **AND** 不同边界环之间不得产生连接

### Requirement: 最终 Depth Cutout 保持有效闭合
正厚度输出 SHALL 由未移动的 Front、反向 Rear、Front Side 与 Rear Side 组成，并只焊接已对应的 leaf/side 基座和中间环。零厚度输出 SHALL 只保留 Front，不生成 Rear、midpoint 或 Side 分支。

#### Scenario: 正厚度闭合
- **WHEN** Balloon 或 Uniform 使用正厚度
- **THEN** 输出 SHALL 坐标有限、无开放边、无零面积面且无跨主体 Side
- **AND** face 数 SHALL 等于两张 leaf faces 与两倍 Front boundary edges 之和
- **AND** UVMap、`o_balloon` 与 `o_normal_reduction` SHALL 保持有效

#### Scenario: 零厚度旁路
- **WHEN** 当前模式的厚度为零
- **THEN** 输出 SHALL 是 Boundary Smooth 后的单层 Front
- **AND** 不得求值或输出 Rear、Side ring target、UV pull 与 Side

### Requirement: Side UV 在叶片边界内部过渡
每张 leaf SHALL 将 Corner UV 求值到 Point domain 并执行四次局部 UV Blur，定义内侧方向为 `blurred - original`。Leaf 边缘 Corner UV SHALL 沿内侧方向移动最多 `0.5`，并以边界四圈 influence 向内渐变到零。移动程度 SHALL 使用 `pow(smoothstep(0, 1, max_displacement), 0.5)` 随当前模式的实际最大位移渐入。Side base corners SHALL 继承调整后的 leaf boundary UV；Side top corners SHALL 保持 original boundary UV。

#### Scenario: Front 与 Rear 分别提供连续 Side UV
- **WHEN** 正厚度输出构建两半 Side
- **THEN** Front Side base SHALL 等于调整后的 Front boundary UV
- **AND** Rear Side base SHALL 等于调整后的 Rear boundary UV
- **AND** 两侧 Side top SHALL 保持各自 original boundary UV
- **AND** 中间环 SHALL 允许两半 Side 保留独立 Corner UV

#### Scenario: Leaf 边缘分担 UV 过渡
- **WHEN** boundary UV 与四次 Blur 的结果不同且当前模式使用正厚度
- **THEN** leaf boundary UV SHALL 沿内侧方向最多移动 `0.5`
- **AND** 相邻四圈 SHALL 连续恢复到 original UV
- **AND** influence 带外的 leaf Corner UV SHALL 保持不变

#### Scenario: Thickness 从零连续增加
- **WHEN** 当前模式的实际最大位移从 0 增加到 `1`
- **THEN** leaf UV pull SHALL 以 Smoothstep 后的 `Pow 0.5` 从零增加到完整强度
- **AND** Side top UV SHALL 始终保持 original boundary UV

### Requirement: Front Normal Reduction 随厚度连续变化
Front 的 normal strength SHALL 在零位移时保持 1，并随实际最大位移平滑过渡到既有 Balloon profile；Shell 的目标 normal strength SHALL 保持 1。Rear 与 Side SHALL 继续使用完整 Normal Reduction。

#### Scenario: Thickness 从零连续增加
- **WHEN** 当前模式的实际最大位移从 0 增加到 `1`
- **THEN** Front normal strength SHALL 使用 Smoothstep 后的 `Pow 0.5` 从 1 过渡到目标 profile
- **AND** 不得因正厚度分支首次启用而在 Front 边缘直接跳到完整 Normal Reduction
