## ADDED Requirements

### Requirement: Depth Cutout 平滑循环不创建边界子网格

`O Image Depth Cutout` 的共享 Boundary Smooth Repeat Zone MUST NOT 包含 Separate Geometry、Sample Nearest 或 Sample Index。边界 Position 与 UV 目标 SHALL 仅通过原网格上的字段和 Blur Attribute 计算。

#### Scenario: 正厚度共同平滑

- **WHEN** Front 与 Rear 共同进入 Boundary Smooth
- **THEN** 每轮在两张断开 leaf 的原拓扑上计算边界目标
- **AND** 不创建临时边界 Geometry

#### Scenario: 输出保持稳定

- **WHEN** Depth Cutout 使用零或正厚度、零或正 Boundary Smooth
- **THEN** 输出 Position、UV、拓扑、闭合性与公开属性保持既有行为

### Requirement: Depth Cutout 跳过禁用控制对应的昂贵字段

`O Image Depth Cutout` SHALL 通过 Geometry Switch 让禁用的平滑或厚度分支保持惰性求值。

#### Scenario: 零 Boundary Smooth

- **WHEN** Boundary Smooth 为零
- **THEN** 不计算或存储边界平滑权重

#### Scenario: 零厚度

- **WHEN** 当前模式的 Thickness 为零
- **THEN** 不计算或存储 256 次 Blur 产生的 front normal direction

### Requirement: Depth Cutout 不计算动态焊接距离

`O Image Depth Cutout` MUST NOT 在投影后执行 CONNECTED Merge by Distance，并 SHALL 将最终 ALL Merge by Distance 的 Distance 固定为 `1e-6`，不得从边长统计计算焊接距离。

#### Scenario: 正厚度输出

- **WHEN** Front、Rear 与 Side 合并为最终实体
- **THEN** 仅执行一次 ALL Merge by Distance
- **AND** Distance 输入不连接字段且值为 `1e-6`
