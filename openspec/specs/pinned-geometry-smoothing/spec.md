# pinned-geometry-smoothing Specification

## Purpose
TBD - created by archiving change pin-geometry-node-smoothing. Update Purpose after archive.
## Requirements
### Requirement: 边界平滑固定开启 Pin Sharp 与 Pin Boundary

`O Image Cutout Symmetry` 的 `Seam Smooth`，以及 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` 的 `Boundary Smooth` SHALL 固定使用 `Pin Sharp = 1` 与 `Pin Boundary = 1`，且 MUST NOT 为这两个 pin 新增或修改 modifier 输入。

#### Scenario: 边界点按边界条带松弛

- **WHEN** 平滑命中边界点，包括 Split 形成的切边与对称平面的切缝
- **THEN** 该点的目标位置取自边界条带自身权重 0.5 的一步 Blur
- **AND** 该点不被内部 Blur 结果拖拽，轮廓不因平滑收缩

#### Scenario: 边界顶点仍沿边界移动

- **WHEN** 边界上存在阶梯状顶点
- **THEN** 顶点沿边界移动以消除阶梯
- **AND** 顶点不会被固定在原位

#### Scenario: 尖锐处少动

- **WHEN** 平滑范围内存在法线不连续的尖锐处
- **THEN** 该点的平滑权重乘以 `|Blur(Normal, 10)|`
- **AND** 尖锐处的位移小于同等权重下平坦区域的位移

### Requirement: Fill Smooth 平滑衔接带

`O Image Cutout Symmetry` 的 `Fill Smooth` SHALL 平滑 front 表面与它挤出的侧壁之间的衔接带。锚点 SHALL 是 front 的完整边界带，即外侧轮廓与对称面上的切缝，SHALL 按四圈渐变衰减并覆盖对称轴上的点。该衔接处不是网格边界，因此 MUST NOT 套用 `Pin Boundary`，但 SHALL 保留 `Pin Sharp`。

#### Scenario: 衔接带使用邻域平均

- **WHEN** `Fill Smooth` 大于 0
- **THEN** 受力点按邻域平均松弛，不切换到边界条带目标

#### Scenario: 衔接带保留锐度权重

- **WHEN** 衔接带范围内存在法线不连续的尖锐处
- **THEN** 该点的平滑权重乘以 `|Blur(Normal, 10)|`

#### Scenario: 衔接带覆盖对称轴上的点

- **WHEN** `Fill Smooth` 大于 0
- **THEN** 对称轴上的点与外侧轮廓同样产生面内位移

#### Scenario: 衔接带比两圈更宽

- **WHEN** `Fill Smooth` 大于 0
- **THEN** 从轮廓向内第三圈的点仍然受力
- **AND** 超出配置圈数的点保持原位

### Requirement: 作用范围保持渐变语义

`Boundary Smooth`、`Fill Smooth`、`Seam Smooth` SHALL 继续表示平滑生效的渐变区域与迭代次数，落在范围外的顶点及其 Face Corner UV MUST 保持原值。

#### Scenario: 范围外不动

- **WHEN** 任一平滑的迭代次数大于 0
- **THEN** 落在渐变范围外的顶点位置与输入完全一致
- **AND** 对应 UV、拓扑与其他属性保持不变

#### Scenario: Cutout 轮廓与切边权重差异

- **WHEN** Depth Cutout 同时存在原始轮廓与 Split 切边
- **THEN** Split 切边的 Position 与 UV 使用完整权重
- **AND** 仅受原始轮廓影响的 Position 与 UV 使用 0.1 倍权重
- **AND** Depth Plane 与 Panorama 的轮廓权重保持 1.0

#### Scenario: 关闭平滑

- **WHEN** 迭代次数为 0
- **THEN** 输出几何、UV 与未平滑的基线完全一致

### Requirement: 共享平滑实现

`common/smoothing.py` SHALL 提供单一的平滑构建函数：pin 形态使用边界条带目标与锐度系数，普通形态只使用邻域平均目标；输入存在 `UVMap` 时，该函数 SHALL 同步构建 seam-aware Face Corner UV 松弛。各节点组只提供几何、迭代次数、作用范围、权重、可移动分量与是否 pin；系统 MUST NOT 为单个节点组保留独立的位置或 UV 平滑实现。

#### Scenario: 站点调用一致

- **WHEN** 任一节点组通过 `pinned_smooth` 构建表面平滑
- **THEN** 该组只传入几何、迭代次数、作用范围、权重、允许移动的分量与是否 pin
- **AND** Position 与 UV 的边界条带分支、锐度权重及普通邻域平均目标由共享实现生成

#### Scenario: 对称平面约束

- **WHEN** `O Image Cutout Symmetry` 应用 Fill 或 Seam 平滑
- **THEN** Position 位移限制在对称平面内的分量
- **AND** UV 按同一作用范围松弛且不受位置分量约束
- **AND** 镜像焊接、UV seam 与闭合性保持不变

### Requirement: 属性平滑保持现状

法线平滑、深度模糊、掩码与统计模糊 MUST NOT 纳入 pin，保持既有节点与权重。

#### Scenario: 属性平滑不受影响

- **WHEN** 构建 Depth Cutout、Depth Plane 或 Panorama
- **THEN** 法线平滑与深度模糊的节点结构、迭代次数与权重与变更前一致

### Requirement: 资产与测试同步

源码、保存资产与测试 SHALL 保持一致；几何节点及嵌套组 MUST 保持 Capture Attribute 为零。

#### Scenario: 重建资产

- **WHEN** 执行节点资产构建并在独立 Blender 进程重新加载
- **THEN** 资产与源码构建结果通过相同的行为验证
- **AND** Capture Attribute 检查通过

### Requirement: Pinned smoothing 同步松弛 UV

`pinned_smooth` SHALL 在逐轮松弛顶点位置时同步松弛输入几何已有的 `UVMap`。UV SHALL 使用与 Position 相同的迭代次数、作用范围、最终权重及 boundary pin 选择；系统 MUST 保持 `UVMap` 的 `FLOAT2` Face Corner 语义，且 MUST NOT 跨 UV seam 或 UV island 混合坐标。

#### Scenario: 边界位置与 UV 同步变平滑

- **WHEN** 输入具有 `UVMap`，平滑次数大于 0，且阶梯状边界落在作用范围内
- **THEN** 边界 Position 与对应 UV 均按共享权重逐轮松弛
- **AND** UV 边界的折角量相对输入降低

#### Scenario: Panorama seam 保持隔离

- **WHEN** `pinned_smooth` 的作用范围经过同一空间位置上的不连续 Face Corner UV
- **THEN** seam 两侧分别在各自 UV island 内松弛
- **AND** 系统不把接近 0 与接近 1 的 U 值直接平均到纹理中部

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

### Requirement: Fill influence caches both consumer domains

Shared pinned smoothing SHALL support caching a fixed influence before the repeat as separate Point and Corner internal attributes. Position SHALL consume the Point value, UV SHALL consume the Corner value, and both attributes MUST be removed after the repeat.

#### Scenario: Cached Fill smoothing preserves output

- **WHEN** `O Image Cutout Symmetry` applies Fill smoothing
- **THEN** cached and uncached results have identical Position, UV, topology, and loop order

### Requirement: UV relaxation is capped at four iterations

Shared pinned smoothing SHALL update UV only during the first four repeat iterations. Position smoothing SHALL continue for the full requested iteration count.

#### Scenario: High smoothing count

- **WHEN** the requested smoothing count is greater than four
- **THEN** UV Store Named Attribute evaluates exactly four times
- **AND** later repeat iterations update Position without updating UV

