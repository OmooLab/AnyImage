# selection-rasterization Specification

## Purpose
TBD - created by archiving change simplify-selection-rasterization. Update Purpose after archive.
## Requirements
### Requirement: Selection uses one overlap-preserving fill
系统 SHALL 使用 non-zero winding 栅格化所有 Selection Path，使同方向自交或重复绕行的重叠区域保持选中，并且不得暴露可切换的填充规则。

#### Scenario: Lasso overlaps itself
- **WHEN** Image Tool 或 Cutout 的 Selection 路径以同一方向重复包围一个区域
- **THEN** 该重叠区域在 Viewport 预览和最终 Selection Mask 中均保持选中

#### Scenario: Simple path is selected
- **WHEN** Selection 路径是普通矩形、半平面、凹多边形或不自交 Lasso
- **THEN** 系统产生与既有 non-zero 填充相同的选中区域

### Requirement: Selection Path contains its inversion state
系统 SHALL 使用只包含普通二维点数组和 Invert 的不可变 Selection Path 值在用户手势与实际 Image 或 Cutout 操作之间传递 Selection；该类型 SHALL 保留完整值的 JSON 编解码，但不得包含填充规则。

#### Scenario: Image Tool submits a Selection
- **WHEN** 用户完成 Image Tool 手势
- **THEN** 同一 Operator 把包含 Points 与 Invert 的 Selection Path 直接交给实际图片编辑

#### Scenario: Cutout menu creates Shape operations
- **WHEN** Cutout Pie Menu 为当前点数组创建 Shape 按钮
- **THEN** 菜单将包含 Points 与 Invert 的完整 Path 编码一次，并为每个 Shape Operator 复用同一字符串

#### Scenario: Cutout Shape operation restores the Selection
- **WHEN** 用户点击任一 Cutout Shape 按钮
- **THEN** Shape Operator 从单一 Path JSON 恢复 Points 与 Invert 后再进行栅格化

### Requirement: Selection rasterization uses scanline events
系统 SHALL 通过路径边与扫描行的交点事件构建 non-zero winding Mask，每条路径边不得重复创建扫描行块乘以 Selection 宽度的二维像素比较数组。

#### Scenario: High-resolution Lasso is rasterized
- **WHEN** 系统处理高分辨率图片上的多点 Lasso
- **THEN** 每条边只为实际跨越的扫描行产生端点事件，所有端点完成后每行执行一次水平累计

#### Scenario: Path point count increases
- **WHEN** Selection 画布不变而路径点数增加
- **THEN** 栅格器增加交点事件处理，不按每个新增点重新扫描完整二维 Selection 像素区域

### Requirement: Non-inverted Selection processing stays local
系统 SHALL 对非 Invert Selection 只在裁切后的路径范围内执行填充、抗锯齿、源 Alpha 合并和可见 bounds 计算；抗锯齿范围 MUST 包含固定卷积核所需的边缘 padding。

#### Scenario: Local Selection is rasterized
- **WHEN** 非 Invert Selection 只覆盖源图的一部分
- **THEN** 中间 Mask 和 Alpha 运算范围限制在路径 bounds 及必要的抗锯齿 padding

#### Scenario: Inverted Selection is rasterized
- **WHEN** Selection 启用 Invert
- **THEN** 系统使用完整图片范围表达路径外区域，但仍只累计一次 scanline 事件

### Requirement: Optimized rasterization preserves Mask semantics
系统 MUST 保持现有像素中心判定、Invert、抗锯齿核、Alpha 阈值、空 Selection 警告和最终局部 Selection Mask bounds 语义。

#### Scenario: Selection has source Alpha
- **WHEN** Selection Path 与源图 Alpha 一起栅格化
- **THEN** 系统只保留 Alpha 高于阈值且 non-zero winding Mask 有效的像素，并返回其紧致 bounds

#### Scenario: Selection has no visible pixels
- **WHEN** Selection 与图片范围或可见源 Alpha 没有交集
- **THEN** 系统报告空 Selection，且不向后续 Image、Cutout 或 AI 操作提交结果

#### Scenario: Equivalent Selection is processed
- **WHEN** 相同 Selection Path、源 Alpha、阈值和抗锯齿设置由参考实现与优化实现处理
- **THEN** 两者产生逐值一致的 Mask values 和相同 bounds

