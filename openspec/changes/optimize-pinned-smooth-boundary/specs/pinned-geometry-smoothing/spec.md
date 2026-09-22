## ADDED Requirements

### Requirement: 边界目标使用归一化掩码平滑

`pinned_smooth` SHALL 在原拓扑上以归一化边界掩码 Blur 计算 Position 与 UV 的边界目标，并 SHALL 在同一轮迭代中共享边界归一化字段。边界目标 MUST NOT 依赖临时分离几何、最近点查找或索引回采样。

#### Scenario: Position 与 UV 共享边界归一化

- **WHEN** Pin Boundary 开启且 Position 与 `UVMap` 同步松弛
- **THEN** 两者分别平滑自身的边界掩码值
- **AND** 两者使用同一个已平滑边界掩码作为归一化分母

#### Scenario: 边界条带结果保持等价

- **WHEN** 输入包含阶梯轮廓、切边或多个断开的 leaf
- **THEN** 边界点目标与权重 `0.5` 的边界子网格一步 Blur 在浮点容差内一致

#### Scenario: Position 与 UV 使用同一轮权重

- **WHEN** Pin Sharp 与作用范围共同影响一次迭代
- **THEN** Position 和 UV 从更新前的同一份 Geometry 求值目标与最终权重

### Requirement: 固定边界字段只在循环外求值一次

`pinned_smooth` SHALL 在 Repeat Zone 前计算边界点掩码及其归一化分母，并通过内部临时属性供所有迭代复用。循环结束后 MUST 移除这些属性。

#### Scenario: 多次边界平滑

- **WHEN** Boundary Smooth 大于一
- **THEN** Repeat Zone 内不包含边界检测或标量边界归一化 Blur
- **AND** Position 与 UV 的每轮值 Blur 继续使用当前迭代几何
