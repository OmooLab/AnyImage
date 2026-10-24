## MODIFIED Requirements

### Requirement: Node graph optimization preserves Cutout geometry
除本规范明确把 Depth Cutout 的单段 Wall 拆成两段、调整 leaf 边缘四圈 UV 并重建 Side UV 外，边界复用、center derivation、triangle-only cleanup 与 zero-thickness short-circuit SHALL NOT 改变有限输出的几何、leaf face order、影响带外 leaf UVMap 或公开属性。

#### Scenario: Representative mode and thickness matrix preserves unaffected behavior
- **WHEN** Cutout 与 Depth Cutout 以 Balloon / Uniform、零和正厚度、零和正 Depth Split 及代表性输入形状求值
- **THEN** leaf positions、leaf face order、影响带外 leaf UVMap 和公开属性 SHALL 在既有容差内保持不变
- **AND** 正厚度 Depth Cutout SHALL 只增加中间 Side ring、边缘四圈 UV 过渡与新的 Side UV

#### Scenario: High-density mesh remains closed with thickness
- **WHEN** Depth Cutout 使用超过 4096 个 source vertices 和正厚度
- **THEN** 双向桥接实体 SHALL 保持有限、闭合且无 non-manifold boundary

### Requirement: Bridge mapping uses linear auxiliary work
Source-index lookup、Side ring target、UV pull 与双向 Side 生成 SHALL 随点数和边界边数线性增长，不得为每个点或边复制节点链、执行全网格 nearest 查询或增加嵌套 Repeat Zone。

Bridge UV SHALL 使用单个 FLOAT_VECTOR 域转换将 Corner UV 求值到 Point domain，不得为 U/V 分量分别重复域转换。

Boundary Smooth 与 Bridge UV SHALL 共用在 leaf 分离前计算的四圈 `_o_boundary_falloff`。`_o_boundary_smooth_weight` SHALL 仅表示几何平滑在 cut/outline 规则后的最终程度，不得作为通用范围属性。

#### Scenario: 高密度双向桥接
- **WHEN** Depth Cutout 使用超过 4096 个 source points 的正厚度网格
- **THEN** bridge mapping SHALL 只使用固定数量的字段、排序、采样、Blur Attribute 与两个 Extrude Mesh 节点
- **AND** Front / Rear SHALL 采样同一个 Side ring target，不得分别重复计算 target
- **AND** Side face 数 SHALL 等于 Front boundary edge 数的两倍

### Requirement: Depth Cutout 跳过禁用控制对应的昂贵字段
`O Image Depth Cutout` SHALL 通过 Geometry Switch 让禁用的轮廓平滑或厚度分支保持惰性求值。

#### Scenario: 零 Boundary Smooth
- **WHEN** Boundary Smooth 为零且 Thickness 为正
- **THEN** 不计算或存储 Boundary Smooth Repeat 使用的权重
- **AND** 双向 Side 与 UV pull SHALL 仍正常求值

#### Scenario: 零厚度
- **WHEN** 当前模式的 Thickness 为零
- **THEN** 不计算或存储 256 次 Blur 产生的 front normal direction
- **AND** 不计算 source-index Side ring target、UV pull、Rear geometry 或 Extrude Mesh

### Requirement: Depth Cutout 不计算动态焊接距离
`O Image Depth Cutout` MUST NOT 在投影后执行 CONNECTED Merge by Distance，并 SHALL 将最终 ALL Merge by Distance 的 Distance 固定为 `1e-6`，不得从边长统计计算焊接距离。

#### Scenario: 正厚度输出
- **WHEN** Front、Rear 与两半 Side 合并为最终实体
- **THEN** 仅执行一次 ALL Merge by Distance
- **AND** Distance 输入不连接字段且值为 `1e-6`
- **AND** Merge 前两半 Side 的同源 Top points SHALL 已位于相同 Side ring target Position
