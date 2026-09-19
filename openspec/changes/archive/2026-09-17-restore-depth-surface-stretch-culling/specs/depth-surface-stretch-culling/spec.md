## ADDED Requirements

### Requirement: Depth Surface exposes a stretch multiplier limit
系统 SHALL 仅为 Depth Surface 提供 **Stretch Limit** Factor 输入，范围为 `0–1`、默认值为 `0`，并将它放入 Options Panel。系统 SHALL 以原始边长除以投影后边长得到剩余比例；`0` SHALL 关闭拉伸剔面，正值越大 SHALL 越严格地清理拉伸面。

#### Scenario: Default value preserves the complete surface
- **WHEN** 用户创建 Depth Surface 且保持 Stretch Limit 为 `0`
- **THEN** 系统 SHALL 不因边长比例删除任何 Edge 或 Face

#### Scenario: Other Cutout shapes do not consume the limit
- **WHEN** 当前 Shape 为 Surface、Balloon 或 Depth Balloon
- **THEN** Stretch Limit SHALL 不显示为该 Shape 的有效控制，也 SHALL 不改变其几何结果

### Requirement: Stretch is measured on matching edges around depth projection
系统 SHALL 在 Depth Surface 的 `Set Position` 之前以 Point Domain 捕获 Edge Vertices Distance Field 的原始值，并将同一个未捕获 Field 直接用于 Set Position 后的当前距离。系统 SHALL 在 `原始距离 / 当前距离 < Stretch Limit` 时以 Point Domain 删除对应位置及其相邻 Edge 和 Face。

#### Scenario: Point remains within the threshold
- **WHEN** 一个 Point 上适配后的边长比例不低于 Stretch Limit
- **THEN** 系统 SHALL 保留该 Point 及其相邻拓扑

#### Scenario: Point exceeds the threshold
- **WHEN** 一个 Point 上适配后的边长比例低于 Stretch Limit
- **THEN** 系统 SHALL 删除该 Point 及相邻 Edge 和 Face

#### Scenario: Depth Scale changes the evaluated stretch
- **WHEN** 用户调整 Depth Scale，使同一条 Edge 的投影后长度跨过当前 Stretch Limit
- **THEN** Geometry Nodes SHALL 实时更新该 Edge 及关联 Face 的保留状态

#### Scenario: Lower threshold permits more stretch
- **WHEN** 同一个 Point 的剩余比例不低于 Stretch Limit
- **THEN** 系统 SHALL 保留该 Point 及其相邻拓扑

### Requirement: Stretch culling removes loose topology
系统 SHALL 在删除拉伸 Point 后删除 `Edge Neighbors.Face Count == 0` 的 Edge，并随后删除 `Vertex Neighbors.Face Count == 0` 的 Point。该清理 SHALL 位于 Depth Surface Thickness 与 Smooth 之前，并 SHALL 保留仍属于至少一个 Face 的开放边界。

#### Scenario: Face deletion leaves a single line
- **WHEN** 拉伸剔面后有 Edge 不再属于任何 Face
- **THEN** 系统 SHALL 删除该 Edge，最终 Depth Surface 不包含纯线拓扑

#### Scenario: Edge deletion leaves isolated points
- **WHEN** 松散 Edge 清理后有 Point 不再属于任何 Face
- **THEN** 系统 SHALL 删除该 Point，最终 Depth Surface 不包含孤立点

#### Scenario: Culling creates an open surface boundary
- **WHEN** 一条 Edge 在拉伸剔面后仍属于一个保留的 Face
- **THEN** 系统 SHALL 保留该 Edge，使后续 Thickness 能围绕最终开放边界构建侧壁

### Requirement: Stretch culling preserves Depth Artifact semantics
系统 SHALL 只使用 Geometry Nodes 中投影前后的几何边长完成拉伸判断，并 SHALL 保持 Vector Depth EXR 的 RGB Camera XYZ、Validity Alpha、Depth Metadata 和 Server Job 协议不变。

#### Scenario: Depth Surface evaluates stretch data
- **WHEN** Depth Surface 使用生成的 Vector Depth EXR 求值
- **THEN** 系统 SHALL 从 RGB Camera XYZ 形成投影并比较几何边长，且 SHALL NOT 要求额外 Depth Continuity 通道或贴图
