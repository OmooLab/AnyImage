# depth-cutout-volume Specification

## Purpose
TBD - created by archiving change reorganize-cutout-shapes. Update Purpose after archive.
## Requirements
### Requirement: 平滑背面保留空间位置
O Image Depth Cutout 的 Balloon 模式 SHALL 以投影正面减 o_balloon 估计中心位置，固定轮廓与切口并平滑内部中心场，再用该中心场与 Balloon 轮廓构造背面。关闭边缘与整体平滑时，正面 MUST 保持原深度表面位置。

#### Scenario: 带噪声的已知体积
- **WHEN** 输入正面由线性变化的中心深度、Balloon 轮廓和内部高频噪声构成，Thickness 为 1，额外几何平滑关闭
- **THEN** 背面接近中心深度减 Balloon 轮廓，背面噪声 RMS 小于正面噪声的 1%，正面顶点位置误差小于 0.00001 个局部单位

#### Scenario: 前后距离保留
- **WHEN** 输入有宽厚主体和处于不同深度的细长结构
- **THEN** 背面形成按轮廓变化的厚度，各部分保留局部前后位置，不统一回到同一个参考平面

### Requirement: 两种厚度方式保留深度表面
深度 Cutout SHALL 在 Balloon 模式使用平滑背面，在 Uniform 模式保留原 Depth Surface 的等厚行为；两种方式的零厚度 SHALL 输出单层深度表面。

#### Scenario: 零厚度
- **WHEN** 两种厚度方式分别设为零
- **THEN** 输出相同投影与 Split 结果的单层深度表面，不生成重叠背面或零面积侧壁

#### Scenario: 等厚方式
- **WHEN** 选择 Uniform 并设为正厚度
- **THEN** 正背面保持原 Depth Surface 的沿内向轴等厚关系

### Requirement: Split 使用投影后的深度落差
Split SHALL 以原始相邻面采样距离差乘 Depth Scale 与变形前跨度比较，Cleanup MUST 位于 Split 前；Depth Scale SHALL 决定切边的可见落差，因此也决定切边是否存在。

#### Scenario: Depth Scale 缩放切边
- **WHEN** 固定输入和 Split，将 Depth Scale 从 0 增大到 1
- **THEN** 零厚度输出在 Depth Scale 为 0 时没有切边，切边随 Depth Scale 增大出现，深度位移随之变化

#### Scenario: 保留分离产生的小片
- **WHEN** 原平面岛面积通过 Cleanup，但 Split 后的部分小片低于该面积阈值
- **THEN** 这些分离小片仍被保留并参与后续厚度构造

### Requirement: 厚度网格闭合且轮廓无固定厚边
正厚度网格 SHALL 在原轮廓合并正背面，并独立封闭 Split 切口；SHALL 保留原型中的深凹比例厚度下限、边缘平滑和整体 Smooth，且不提供 Rim Thickness。

#### Scenario: 五张实图验收
- **WHEN** 使用噬菌体、蜘蛛、幼虫、心脏、棕榈树缓存输入，分别求值无平滑、边缘与整体平滑、平滑加 Split
- **THEN** 15 个正厚度组合均为有限坐标、无非流形边、无法线连接错误和零面积面，输出保留 UVMap 与 o_balloon 并移除专用暂存属性

#### Scenario: 边缘与整体控制
- **WHEN** 调整 Edge Smooth、Smooth 和 Smooth Iterations
- **THEN** 相应几何平滑生效，Smooth Iterations 为零时整体平滑不改变位置，原轮廓不产生固定厚度的边框

