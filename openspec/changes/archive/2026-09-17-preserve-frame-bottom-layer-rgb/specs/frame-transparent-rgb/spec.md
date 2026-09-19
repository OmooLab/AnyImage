## ADDED Requirements

### Requirement: Frame selects the bottom valid source for hidden RGB

Frame SHALL 在每个输出像素复用当前有效投影和从远到近的稳定深度顺序，以第一个几何有效样本作为底层 RGB 来源。底层判定 SHALL 独立于 Alpha，并 SHALL 沿用相同深度时 active 位于最上层、其他对象按名称稳定排序的规则。

#### Scenario: Transparent foreground overlaps a transparent background
- **WHEN** 蓝色底层和红色前景覆盖同一像素，且两者 Alpha 都为零
- **THEN** 输出 RGB SHALL 为底层蓝色
- **AND** 输出 Alpha SHALL 为零

#### Scenario: The farthest image does not cover a pixel
- **WHEN** 最远图片在某像素没有有效投影，而其他图片具有有效投影
- **THEN** 该像素的底层来源 SHALL 为实际覆盖它的最远有效图片

#### Scenario: Transparent images share the same depth
- **WHEN** active 与另一透明图片在相同深度覆盖同一像素
- **THEN** 底层 RGB SHALL 来自非 active 图片
- **AND** 多个非 active 同深度图片 SHALL 沿用现有名称排序确定底层

#### Scenario: Source planes cross
- **WHEN** 两张透明图片的平面相交，并在不同像素交换前后关系
- **THEN** 各像素的隐藏 RGB SHALL 分别来自该像素处最底层的有效图片

#### Scenario: Projection validity depends on the view mode
- **WHEN** 一个候选底层在透视视图中位于观察方向后方，或无法取得有限且位于源边界内的交点
- **THEN** 该样本 SHALL 不作为底层来源
- **AND** 正交视图中有限且位于源边界内的非正深度交点 SHALL 继续具有底层资格

### Requirement: Frame preserves bottom RGB in transparent output

Frame SHALL 在最终 straight RGBA 转换后 Alpha 为零且具有有效源覆盖的像素中，保存底层源未乘 Alpha 的 RGB 双线性采样结果。采样 SHALL 使用现有 Frame 投影坐标和边界约定；系统 SHALL 保持当前 Alpha 可见性数值判定与最终 Alpha 结果。

#### Scenario: A masked single image is framed without resampling displacement
- **WHEN** 单张图片经 Mask 剔除 Alpha 后，以原尺寸和像素中心对齐的映射执行 Frame
- **THEN** 透明区域的 RGB SHALL 与源图片对应像素一致
- **AND** Alpha SHALL 保持剔除后的结果

#### Scenario: Transparent source colors require interpolation
- **WHEN** Frame 缩放或透视映射在底层完全透明区域取得非整数像素采样位置
- **THEN** RGB SHALL 为底层原始 RGB 的双线性插值结果
- **AND** Alpha SHALL 保持零

#### Scenario: Mask Add follows a packed Frame result
- **WHEN** 用户对 Mask 剔除后经 Frame 生成的单图 Packed Image 执行 Mask Add
- **THEN** 提升 Alpha 的区域 SHALL 显示 Frame 保留的底层颜色
- **AND** 该颜色 SHALL 在 Packed Image 像素中实际存在

### Requirement: Frame blends foreground RGB over bottom color with independent alpha

Frame SHALL 以最底层有效源的原始 RGB 双线性样本初始化颜色，随后从远到近对每个前景计算 C = P_front + C × (1 - A_front)，其中 P_front 为预乘后插值的 RGB。Alpha SHALL 从零开始对包括底层在内的全部有效层独立执行 source-over，并沿用现有数值判定。最终 RGB SHALL 不除以合成 Alpha。

#### Scenario: Both layers are partially transparent
- **WHEN** 蓝色底层 Alpha 为 0.5，红色前景 Alpha 为 0.25
- **THEN** 输出 Alpha SHALL 为 0.625
- **AND** straight RGB SHALL 为红色 0.25、绿色 0、蓝色 0.75

#### Scenario: A visible foreground overlaps a transparent bottom layer
- **WHEN** 蓝色底层 Alpha 为零，红色前景 Alpha 为 0.25
- **THEN** 输出 SHALL 为 RGB (0.25, 0, 0.75) 和 Alpha 0.25
- **AND** 恢复 Alpha 后 SHALL 保留相同 RGB

#### Scenario: Hidden neighbor colors meet a visible sampling edge
- **WHEN** 前景插值邻域同时含有可见红色像素和完全透明绿色像素
- **THEN** 前景采样 SHALL 沿用预乘插值结果并按采样 Alpha 混入底色
- **AND** 隐藏绿色 SHALL 不污染可见红色

#### Scenario: Restoring alpha reveals a continuous transition into white

- **WHEN** 前景原图的黑色背景被 Alpha 隐藏，前景边缘 Alpha 逐渐下降，且底层原始 RGB 为白色、Alpha 为零
- **THEN** RGB SHALL 随前景 Alpha 连续过渡到白色
- **AND** Packed Image 经 Mask Add 恢复 Alpha 后 SHALL 保留该过渡

### Requirement: Source coverage takes priority over edge color extension

Frame SHALL 保持完整 Canvas 和源外透明边缘扩色。存在有效源覆盖且最终透明的像素 SHALL 使用底层 RGB；没有有效源覆盖的像素 SHALL 保持 Alpha 零，并沿用紧邻可见内容的一圈 RGB 扩色，其余区域保持透明黑色。

#### Scenario: Transparent source pixels border visible content
- **WHEN** 源内部透明像素紧邻可见像素，且隐藏 RGB 与相邻可见颜色不同
- **THEN** 源内部透明像素 SHALL 保留底层原始 RGB
- **AND** 该 RGB SHALL 不被边缘扩色覆盖

#### Scenario: The frame extends beyond all source images
- **WHEN** Frame 包含所有源投影之外的区域
- **THEN** 外部像素 Alpha SHALL 为零
- **AND** 一圈扩色之外的无覆盖像素 SHALL 为透明黑色
- **AND** Canvas 尺寸 SHALL 保持原有 Frame 规则

#### Scenario: A visible edge crosses a processing chunk boundary
- **WHEN** 可见边缘跨越 Frame 行块边界
- **THEN** 透明边缘颜色 SHALL 与使用同一规则处理完整画布的结果一致
