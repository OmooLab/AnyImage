# boundary-depth-smoothing Specification

## Purpose
TBD - created by archiving change unify-boundary-depth-smoothing. Update Purpose after archive.
## Requirements
### Requirement: Shared Boundary Smooth control

`O Image Depth Cutout`、`O Image Depth Plane`、`O Image Depth Panorama` SHALL 保留 `Boundary Smooth` 输入，Depth Cutout 默认值为 2，另外两组为 5；Cutout 范围为 1–20，另外两组为 0–20。Depth Cutout 使用它控制每轮深度 Blur 的步数和现有边界网格平滑次数；另外两组使用它控制深度 Blur 与网格平滑次数。

#### Scenario: Positive iteration count
- **WHEN** 用户将任一组的 Boundary Smooth 设为 12
- **THEN** 每批深度 Blur 和现有边界网格平滑均使用 12 次迭代
- **AND** Depth Cutout 的批次数由 Outline Depth Fix 控制

#### Scenario: Disabled smoothing
- **WHEN** Boundary Smooth 为 0
- **THEN** 输出几何与两种边界平滑均关闭的基线一致
- **AND** 深度采样直接使用原值

### Requirement: Topology-local scalar smoothing

系统 SHALL 在有效性剔除及 Split 后、投影前的网格 Point 域对深度标量执行 Blur，并在可处理边界及邻近两圈内应用结果。Depth Plane 和 Panorama 的 Blur Weight 为 0.5；Depth Cutout 使用当前残差计算的自适应权重。边界影响范围 SHALL 由边界字段的 2 次 Weight 为 1 的 Blur 与原边界字段取最大值后，排除保护点得到。

#### Scenario: Isolated boundary spike
- **WHEN** 原本平缓的表面在一个可处理边界点具有深度尖刺并启用 Boundary Smooth
- **THEN** 深度突变通过当前网格邻域的标量平均减弱
- **AND** 深度平滑阶段的顶点、边、面及 UV 拓扑保持不变

#### Scenario: Interior preservation
- **WHEN** 顶点位于影响范围之外
- **THEN** 深度平滑阶段直接保留其原采样值

#### Scenario: Deleted and separated samples
- **WHEN** 邻近像素所属网格已被有效性剔除，或邻接表面已由 Split 分离
- **THEN** 平滑仅使用当前连通网格的样本，不跨已删区域或分离表面平均

### Requirement: Cutout silhouette depth smoothing

Depth Cutout SHALL 仅将原 Alpha 轮廓及内侧两圈纳入自适应深度平滑，保护 Split 切边及其与原轮廓的交点。后置网格平滑保持既有职责。对外轮廓术语 SHALL 统一使用 Outline，与 Fine Outline 一致。

#### Scenario: Adaptive batches
- **WHEN** Outline Depth Fix 大于 0 且 Boundary Smooth 大于 0
- **THEN** 每轮根据当前相机深度与 Weight 0.5 的一步 Blur 之差，乘 Uniform Scale 后除以置换前、Split 清理后所有网格边长的中位数
- **AND** Ratio 固定以 0.25–0.5 的 Smoothstep 映射到 0–1，并乘轮廓影响范围
- **AND** Weight 不再 Blur，批内固定使用 Boundary Smooth 次，每轮重新计算
- **AND** Outline Depth Fix 默认 16，范围 0–200；0 关闭轮廓深度处理

#### Scenario: Split boundary preservation
- **WHEN** Split 在原轮廓内形成新的切边
- **THEN** 深度平滑保持这些切边的相机采样不变，包括与原轮廓相交的切分点

#### Scenario: Fine Outline with zero thickness
- **WHEN** Fine Outline 的原轮廓存在异常深度，Thickness 为 0 且 Boundary Smooth 大于 0
- **THEN** 原轮廓点的深度参与平滑
- **AND** 深度平滑后的相机投影轮廓在浮点容差内保持一致

### Requirement: Depth Plane rectangle protection

Depth Plane SHALL 对有效性剔除或 Split 形成的可处理边界应用深度平滑，并同时从边界起点和最终应用权重中排除原 UV 矩形外框。

#### Scenario: Alpha or model-validity opening
- **WHEN** Valid Only 因 Alpha 或模型 validity 删除网格并形成新开口
- **THEN** 新开口及邻近两圈参与深度平滑
- **AND** 保留下来的原矩形外框点保持既有保护行为

#### Scenario: Intact rectangle
- **WHEN** Valid Only 和 Split 均关闭，网格仅有原矩形外边界
- **THEN** 新增深度 Blur 对输出不产生变化

### Requirement: Projection-aware reconstruction

Cutout 和 Depth Plane SHALL 在深度平滑阶段保持原相机射线，通过平滑后的 Z 重建相机点；Depth Panorama SHALL 平滑径向距离并保持原球面方向。方向保持以现有后置网格平滑之前的结果为准。

#### Scenario: Camera depth reconstruction
- **WHEN** 正的有效相机 Z 被平滑
- **THEN** 新旧相机点的 X/Z、Y/Z 在浮点容差内一致

#### Scenario: Degenerate camera depth
- **WHEN** 原采样 Z 无法安全用于比例重建
- **THEN** 保留原采样，不因深度平滑产生非有限值

#### Scenario: Panorama seam and poles
- **WHEN** 有效表面跨越经度接缝或覆盖极点
- **THEN** 深度 Blur 使用实际球面邻接，不将 UV 接缝当作网格开口
- **AND** 径向重建保持每个点的球面方向

#### Scenario: Retained invalid panorama region
- **WHEN** Panorama 关闭 Depth Mask 保留无效区域
- **THEN** 无效面整片落在 `Dome Radius`
- **AND** 该距离不混入有效边界的径向平均

### Requirement: Integrated geometry and asset verification

系统 SHALL 保持厚度、Split、Depth Scale、UV、材质和用户属性的既有职责，所有几何节点及嵌套组 MUST 保持 Capture Attribute 为零。更新后的节点源码、行为测试及保存资产 SHALL 一致。

#### Scenario: Surface modes and downstream shaping
- **WHEN** 三个深度表面组合使用边界平滑与自身支持的 Split、Depth Scale、厚度或 Cutout 模式
- **THEN** 输出为有效几何，属性和材质传递符合原有协议
- **AND** 深度平滑不改变有效性剔除与 Split 的拓扑判定

#### Scenario: Rebuilt asset
- **WHEN** 执行节点资产构建并在独立 Blender 进程中重新加载保存资产
- **THEN** 资产与源码构建结果通过相同的行为验证
- **AND** 公共参数、节点连接和 Capture 禁用检查通过

### Requirement: Simplified Cutout shaping controls

Depth Cutout SHALL 固定前后法线平滑为 100 次，原联动宽范围滤波固定为 512 次；移除 Normal Smooth 输入。系统 SHALL 删除 Edge Round 输入及对应前表面位移、厚度补偿和圆化字段，保留 Split 基础收口。

#### Scenario: Reduced interface
- **WHEN** 新建 Depth Cutout
- **THEN** Outline Depth Fix 默认 16、Boundary Smooth 默认 2
- **AND** 输入中没有 Edge Round、Normal Smooth 或 Outline Smooth Iterations

### Requirement: Cutout Options order and inflation factor

Depth Cutout 的 Options SHALL 按 Cleanup Threshold、Smooth Weight、Reference Depth、Boundary Smooth、Outline Depth Fix、Front Inflation 排列。Front Inflation SHALL 为 0–1 Factor、默认 0；Boundary Smooth SHALL 为 1–20、默认 2。

#### Scenario: New Cutout defaults
- **WHEN** 新建 Depth Cutout
- **THEN** Front Inflation 为 0，Boundary Smooth 不能从界面设为小于 1
- **AND** Outline Depth Fix 保持默认 16

