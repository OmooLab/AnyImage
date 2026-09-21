## ADDED Requirements

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

## MODIFIED Requirements

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
