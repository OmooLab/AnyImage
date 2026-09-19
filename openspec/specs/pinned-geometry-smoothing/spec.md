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

`Boundary Smooth`、`Fill Smooth`、`Seam Smooth` SHALL 继续表示平滑生效的渐变区域与迭代次数，落在范围外的顶点 MUST 保持原位。

#### Scenario: 范围外不动

- **WHEN** 任一平滑的迭代次数大于 0
- **THEN** 落在渐变范围外的顶点位置与输入完全一致
- **AND** 拓扑与 UV 保持不变

#### Scenario: Cutout 轮廓与切边权重差异

- **WHEN** Depth Cutout 同时存在原始轮廓与 Split 切边
- **THEN** Split 切边使用完整权重
- **AND** 原始轮廓使用 0.1 倍权重
- **AND** Depth Plane 与 Panorama 的轮廓权重保持 1.0

#### Scenario: 关闭平滑

- **WHEN** 迭代次数为 0
- **THEN** 输出几何与未平滑的基线完全一致

### Requirement: 共享平滑实现

`common/smoothing.py` SHALL 提供单一的平滑构建函数：pin 形态使用边界条带目标与锐度系数，普通形态只使用邻域平均目标。各节点组只提供几何、迭代次数、作用范围、权重、可移动分量与是否 pin；系统 MUST NOT 为单个节点组保留独立的平滑实现或旧偏移路径。

#### Scenario: 站点调用一致

- **WHEN** 任一节点组构建顶点位置平滑
- **THEN** 该组只传入几何、迭代次数、作用范围、权重、允许移动的分量与是否 pin
- **AND** 边界条带分支、锐度权重与普通邻域平均目标由共享实现生成

#### Scenario: 对称平面约束

- **WHEN** `O Image Cutout Symmetry` 应用 Fill 或 Seam 平滑
- **THEN** 位移限制在对称平面内的分量
- **AND** 镜像焊接与闭合性保持不变

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

