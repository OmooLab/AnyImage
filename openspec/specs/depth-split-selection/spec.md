# depth-split-selection Specification

## Purpose
TBD - created by archiving change scale-depth-split-by-depth-scale. Update Purpose after archive.
## Requirements
### Requirement: Depth Split 使用投影后的几何落差
Depth Split 的判定 SHALL 以原始相邻面采样距离差乘 Depth Scale 作为落差量，与变形前的采样跨度比较；平均射线距离 SHALL 继续作为把绝对差归一化为相对跳变的因子，Depth Scale MUST NOT 参与该归一化。参数说明 MUST 说明切边随 Depth Scale 缩放。

#### Scenario: Depth Scale 为零
- **WHEN** 固定深度图与 Depth Split，把 Depth Scale 设为 0
- **THEN** 输出拓扑与 Split 为 0 时相同，没有切边，也没有条带面被删除

#### Scenario: Depth Scale 放大落差
- **WHEN** 同一输入在 Depth Scale 从 0 增大到 1 之间求值
- **THEN** 选中的切边只增不减，Depth Scale 为 1 时与当前判据结果一致

#### Scenario: 深度数据整体缩放
- **WHEN** 同一深度图的采样数值整体乘以任意正数
- **THEN** 选中切边完全相同

### Requirement: 三个深度资产共用同一判据
`O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` SHALL 使用同一个 Depth Split 判据并各自传入自己的 Depth Scale。

#### Scenario: 资产一致性
- **WHEN** 三个资产分别求值，Depth Scale 设为零或设为 1
- **THEN** 三者都表现为零不切开、1 与改动前一致

