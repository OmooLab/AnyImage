## ADDED Requirements

### Requirement: 深度节点组不公开 Smooth Weight

`O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` SHALL 不在公开接口中提供 `Smooth Weight`，边界平滑 MUST 按完整影响场混合顶点位置。

#### Scenario: 检查节点组接口

- **WHEN** 读取三个节点组的输入接口
- **THEN** 接口不存在 `Smooth Weight`，且 `Boundary Smooth` 仍控制边界平滑迭代次数

#### Scenario: 默认边界平滑结果

- **WHEN** 用户保持默认参数并提高 `Boundary Smooth`
- **THEN** 边界带内的顶点按影响场强度移动到平滑位置，影响带外的顶点保持不变

### Requirement: 共享平滑构建只保留影响场形态

`expand_smooth()` SHALL 只接受迭代次数输入、影响场与几何，并 MUST 在迭代次数为零时原样返回输入几何。

#### Scenario: 迭代次数为零

- **WHEN** `Boundary Smooth` 为 0
- **THEN** 输出几何与输入几何完全一致

### Requirement: Options 中的 Reference Depth 位于最后

包含 `Reference Depth` 的节点组 SHALL 在 Options 面板最后一项提供该输入，其余 Options 控制项 MUST 保持各自职责与默认值。

#### Scenario: 检查 Depth Plane 与 Depth Cutout 排列

- **WHEN** 读取 `O Image Depth Plane` 与 `O Image Depth Cutout` 的 Options 项顺序
- **THEN** 最后一项为 `Reference Depth`，之前的项依次为各自的艺术调整参数

#### Scenario: 检查 Relief Plane 排列

- **WHEN** 读取 `O Image Relief Plane` 的 Options 项顺序
- **THEN** 项顺序为 `Mask Threshold`、`Reference Depth`

### Requirement: Reference Depth 保持既有几何含义

移动面板位置 SHALL 不改变 `Reference Depth` 的类型、子类型、默认值、范围与几何运算方式。

#### Scenario: 校验输入属性

- **WHEN** 读取 `Reference Depth` 输入
- **THEN** 该输入使用 `DISTANCE` 子类型，并继续作为采样深度的运算基准
