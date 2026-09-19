## ADDED Requirements

### Requirement: Relief depth is clamped at the thickness height
`O Image Relief Plane` SHALL 将未置换可变面所在的 `Thickness` 高度定义为 depth 0。经过参考深度矫正、方向换算和 `Depth Scale` 得到的最终浮雕位移 MUST 不小于零，使可变面不进入固定底面与 `Thickness` 高度之间的基础厚度区域。

#### Scenario: Far depth would move below depth zero
- **WHEN** 矫正参考深度与采样深度之差经过方向换算和缩放后小于零
- **THEN** 可变面的最终浮雕位移钳制为零
- **AND** 可变面位于 `Thickness` 高度

#### Scenario: Positive relief depth
- **WHEN** 矫正参考深度与采样深度之差经过方向换算和缩放后大于零
- **THEN** 可变面保留完整的正向浮雕位移
- **AND** 正向位移不受 `Thickness` 大小限制

#### Scenario: Keep the fixed base
- **WHEN** `Thickness` 大于零且浮雕深度发生变化
- **THEN** 固定底面的所有顶点保持在对象空间 `Z=0`
- **AND** 侧壁各层按其从固定底面到可变面的归一化位置线性应用最终浮雕位移

### Requirement: Relief Plane exposes a reference depth correction
`O Image Relief Plane` SHALL 在主界面公开 `Depth Offset` 距离输入，默认值为 `1` 并允许正负值。`Depth Direction` 与 `Depth Offset` SHALL 移出 Options，并在 `Thickness` 后按 `Depth Direction`、`Depth Offset`、`Depth Scale` 排列。系统 SHALL 先按 `Reference Depth + Depth Offset` 得到矫正参考深度，再进行 `Depth Direction` 参考平面换算、与缩放采样深度求差及 `Depth Scale` 缩放，最后把负位移钳制为零。

#### Scenario: Use the default offset
- **WHEN** `Depth Offset` 为默认值 `1`
- **THEN** 矫正参考深度等于 `Reference Depth + 1`
- **AND** 系统按现有方向换算和 `Depth Scale` 计算浮雕位移
- **AND** 最终结果仍钳制在 depth 0

#### Scenario: Increase the reference depth correction
- **WHEN** 用户增加 `Depth Offset`
- **THEN** 系统在方向换算和 `Depth Scale` 之前增加矫正参考深度
- **AND** Depth Offset 对最终位移的影响随 `Depth Scale` 一同缩放

#### Scenario: Decrease the reference depth correction
- **WHEN** 用户减小 `Depth Offset`
- **THEN** 系统在方向换算和 `Depth Scale` 之前减小矫正参考深度
- **AND** 任何结果均不低于 depth 0

#### Scenario: Apply depth direction after correction
- **WHEN** `Depth Offset` 非零且用户改变 `Depth Direction`
- **THEN** 系统使用包含 Depth Offset 的矫正参考深度构建方向调整后的参考平面
- **AND** 随后才计算相对深度和应用 `Depth Scale`

### Requirement: Depth Scale uses depth zero as its invariant origin
`Depth Scale` SHALL 以 depth 0 为几何位移基准，缩放包含 `Depth Offset` 矫正的相对深度差，MUST 不缩放 `Thickness` 高度本身。

#### Scenario: Set depth scale to zero
- **WHEN** `Depth Scale` 为 `0`
- **THEN** 采样深度差、`Reference Depth` 和 `Depth Offset` 均不产生几何位移
- **AND** 可变面位于 `Thickness` 高度

#### Scenario: Change depth scale
- **WHEN** 用户改变 `Depth Scale` 且保持 `Thickness`、`Reference Depth` 和 `Depth Offset` 不变
- **THEN** 系统以 depth 0 为基准缩放包含 Depth Offset 矫正的采样深度差
- **AND** `Thickness` 所在高度保持不变

### Requirement: Relief Plane initializes an approximate depth direction
系统 SHALL 在创建 Relief Plane 时，将完整深度图的有效像素映射到图片平面局部坐标，以 `Uniform Scale` 换算深度并进行稳健平面拟合，再用拟合平面的归一化方向初始化 `Depth Direction`。Relief Plane 与 Cutout Symmetry MUST 共用同一平面拟合实现。

#### Scenario: Create a relief from a sloped depth field
- **WHEN** 有效深度场包含可拟合的整体斜率
- **THEN** 新建 Relief Plane 的 `Depth Direction` 使用拟合斜率对应的归一化方向
- **AND** `Depth Offset` 保持默认值 `1`

#### Scenario: Create a relief from a flat depth field
- **WHEN** 有效深度场整体为平面且没有斜率
- **THEN** 新建 Relief Plane 的 `Depth Direction` 近似为 `(0, 0, 1)`

#### Scenario: Create a relief without usable depth samples
- **WHEN** 深度图没有可用于拟合的正有限深度
- **THEN** Relief Plane 仍然成功创建
- **AND** `Depth Direction` 回退为 `(0, 0, 1)`
