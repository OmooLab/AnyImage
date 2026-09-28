## ADDED Requirements

### Requirement: Cutout 图片使用固定上下双区布局

系统 SHALL 将 Cutout 的 Color 与 Normal 图片生成为 `W × 2H`，其中上半区为 Front，下半区为水平镜像的 Rear。Depth SHALL 保持单张 `W × H` 正面图片。该布局 MUST 仅用于 Cutout，不得改变其他图片创建入口。

#### Scenario: 创建无 AI 的普通 Cutout
- **WHEN** 用户从 `W × H` 裁切内容创建不带 Normal 的 Flat 或 Solid
- **THEN** 材质 Color Image 尺寸为 `W × 2H`
- **AND** 下半区是上半区的水平镜像

#### Scenario: 创建带完整 AI 产物的 Depth Cutout
- **WHEN** 用户创建需要 Color、Object Normal 与 Depth 的 Depth Cutout
- **THEN** Color 与 Object Normal 使用上下双区布局，Depth 保持单区
- **AND** Object Normal 后片只镜像像素位置，不改变对象空间向量通道

#### Scenario: 非 Cutout 图片入口
- **WHEN** 用户创建 Plane、Depth Plane、Relief Plane、Panorama 或 Clipboard Plane
- **THEN** 对应图片尺寸和完整 0–1 UV 保持既有单区协议

### Requirement: Boundary Padding 先于材质 Atlas

系统 SHALL 在 Color 与 Depth 仍为 `W × H` 单区图片时执行既有 Boundary Padding，随后才将 Color 与 Normal 组成 `W × 2H` Atlas。Normal SHALL 延续既有行为，不参与 Boundary Padding；Depth SHALL 在 Padding 后保持单区。

#### Scenario: 创建启用 Boundary Padding 的 Cutout
- **WHEN** 系统已经根据 BaseShape 得到单区内容 mask
- **THEN** Boundary Padding 使用该 mask 处理单区 Color 与 Depth
- **AND** Color Padding 完成后才建立上下双区 Atlas
- **AND** Normal 不经过 Boundary Padding，只建立上下双区 Atlas
- **AND** Depth Padding 完成后仍为 `W × H`

### Requirement: Cutout 正片与后片使用独立 UV 区域

Cutout 基础 Front UV SHALL 位于上半区，映射为 `(u, 0.5 + 0.5v)`。节点组生成 Rear 时 SHALL 将对应 Face Corner UV 映射到下半区 `(1-u, 0.5v)`，并 MUST 保持正背位置一一对应。

#### Scenario: 零厚度单片
- **WHEN** O Image Cutout 或 O Image Depth Cutout 的当前厚度模式为零
- **THEN** 输出只有 Front 表面
- **AND** 所有材质 UV 均位于上半区

#### Scenario: Balloon 生成双面
- **WHEN** Balloon Thickness 为正并生成 Front、Rear 与 Side
- **THEN** Front corners 位于上半区，Rear corners 位于下半区
- **AND** 对应正背 corners 的 U 互为 `1-u`、V 相差 `0.5`

#### Scenario: Shell 生成双面
- **WHEN** Shell Thickness 为正并生成 Front、Rear 与分段 Side
- **THEN** Front 与 Rear 使用相互独立且一一对应的上下区域

#### Scenario: 后置对称生成镜像侧
- **WHEN** Depth Cutout 经过 Cutout Symmetry 生成 Mirrored side
- **THEN** Retained side 与 Mirrored side 使用相同的输入 UV
- **AND** 两侧各自保留输入中已有的 Front 上区与 Rear 下区分类
- **AND** 对称焊接不合并 Face Corner UV seam

### Requirement: Cutout 侧壁按叶片来源分区

普通 Cutout 与 Depth Cutout 的 Side SHALL 按挤出来源分为 Front-side 与 Rear-side。后置对称 SHALL 区分 Retained side 与 Mirrored side。上区与下区 SHALL 在连接位置保留 Face Corner UV seam；任何单个 Side face MUST NOT 在两个 tile 之间插值。

#### Scenario: 两张叶片分别挤向 Side 中圈
- **WHEN** Balloon 或 Shell 以正厚度生成闭合侧壁
- **THEN** Front 叶片产生的 Side faces 全部使用上半区，Rear 叶片产生的 Side faces 全部使用下半区
- **AND** 两组 Side 在共同中圈保持几何连接但具有不连续 Face Corner UV

#### Scenario: 原 Side face 直接跨越正背
- **WHEN** 普通 Cutout 的既有构造会产生从 Front 直接连接到 Rear 的 Side face
- **THEN** 系统在 Side 中点分开 Front-side 与 Rear-side
- **AND** 不存在 corners 同时落入上下两个 tile 的单张 Side face

#### Scenario: 编辑后片图片
- **WHEN** 用户修改 Atlas 下半区而不修改上半区
- **THEN** Rear 材质采样发生变化
- **AND** Rear-side 随 Rear 变化，Front 与 Front-side 的采样保持不变

### Requirement: 双区布局不改变几何语义

上下复制 SHALL 仅提供独立材质地址空间。Depth 后片 SHALL 继续由现有 Balloon、Shell 或对称算法生成，系统 MUST NOT 将下半区 Depth 解释为独立背面预测。

#### Scenario: 比较布局变更前后的几何
- **WHEN** 相同单张正面输入以相同 Cutout 形态和节点参数求值
- **THEN** 可见表面位置、面方向、厚度和 Split 结果与旧重叠 UV 协议一致
- **AND** 除普通 Cutout 为 Side 分区所需的中圈拓扑外，仅图片高度与 Face Corner UV 分区发生变化
