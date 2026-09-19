# mask-editing Specification

## Purpose
TBD - created by archiving change add-live-mask-preview-and-polyline. Update Purpose after archive.
## Requirements
### Requirement: Mask exposes three gestures with Subtract by default
系统 SHALL 在单一 Mask Tool 中提供 Lasso、Brush 和 Polyline Gesture，并 SHALL 提供 Set、Add、Subtract Mode。新 Scene 的 Mask Mode MUST 默认为 Subtract；已有 Scene 中已保存的 Mode MUST 保持其值。Radius MUST 只在 Brush Gesture 下显示和生效。

#### Scenario: New scene uses Subtract
- **WHEN** 新 Scene 尚未保存 Mask Mode
- **THEN** Mask Tool Settings 与新启动的 Mask Operator 使用 Subtract

#### Scenario: Gesture settings remain unified
- **WHEN** 用户在 Lasso、Brush 与 Polyline 之间切换
- **THEN** 系统仍使用同一个 Mask Tool、Mode 设置和 Alpha 合成入口，并只在 Brush 下显示 Radius

### Requirement: Brush defers Image work until release
Brush MUST 在手势完成前保持 active Image Empty 的 Image 不变。拖动期间 MUST NOT 读取源 RGBA、创建临时 Image、栅格化图片级 Mask、写入 Pixel Buffer、调用 `image.update()` 或 Pack；鼠标释放后 SHALL 一次性计算并提交结果。

#### Scenario: Dragging leaves the Image untouched
- **WHEN** 用户按住左键移动 Brush 且手势尚未完成
- **THEN** active Image Empty 继续显示并引用操作开始时的 Image，只通过 Viewport Overlay 呈现待提交范围

#### Scenario: Shared source remains unchanged during the gesture
- **WHEN** active Image Empty 与另一个对象共享源 Image 并开始 Brush
- **THEN** 两个对象都继续引用且显示原始 Image，直到 active Image Empty 在释放后接收新结果

#### Scenario: Stationary hold performs no Image work
- **WHEN** 用户按住 Brush 且鼠标没有产生有效位移
- **THEN** 系统不执行 Image 更新或图片级计算

### Requirement: Brush completion and cancellation are transactional
Brush 完成时 MUST 创建并 Pack 一个最终结果 Image，并 SHALL 通过公共替换入口让 active Image Empty 承载结果。取消、工具切换或错误 MUST 保持源 Image 不变且不产生完成的编辑；成功完成 MUST 保持对象 identity、matrix、display size、offset、共享源引用和单步 Undo 语义。

#### Scenario: Completing a Brush persists one result
- **WHEN** 用户释放左键完成 Brush
- **THEN** 系统计算完整覆盖、创建并 Pack 一个同尺寸结果，active Image Empty 的画框和对象身份保持不变

#### Scenario: Cancelling restores the source
- **WHEN** 用户在 Brush 期间按 RMB 或 Esc
- **THEN** active Image Empty 仍引用操作前 Image，且没有临时 Image 或完成的 Undo 编辑

#### Scenario: Tool switch cleans the preview
- **WHEN** Brush 运行期间 active WorkspaceTool 发生变化
- **THEN** 系统只结束 Overlay 与 Modal，Image 保持不变

### Requirement: Brush uses one continuous primitive union
Brush MUST 从简化后的屏幕轨迹生成圆形采样点和等宽连接条。Overlay 与释放后的 Selection MUST 使用同一组 Primitive 和 union 语义；急转、折返、自交与重叠区域 MUST 保持连续，MUST NOT 出现超出 Radius 的尖角或未填充三角。图片空间 union MUST 以逐像素最大值累计到单个覆盖画布，不得保存逐 Primitive Mask 列表。

#### Scenario: Sparse events leave no gap
- **WHEN** 两个连续 Brush 采样点之间的距离大于 Radius
- **THEN** 两点之间的胶囊完整覆盖连线且不出现空隙

#### Scenario: Turning does not create a horn or hole
- **WHEN** Brush 中心轨迹发生方向变化
- **THEN** 圆形采样点与连接条融合，Overlay 与最终 Selection 都不出现 miter 尖角或未填充三角

#### Scenario: Preview and result share the footprint
- **WHEN** 用户释放 Brush
- **THEN** 系统投影并栅格化拖动时显示的同一组 Brush Primitive，并使用相同的 union 规则

### Requirement: Brush matches the Lasso and Polyline overlay
Brush SHALL 在每个有效鼠标事件后绘制整次未提交笔画的 footprint。Overlay MUST 复用 Lasso、Polyline 的虚线边界、non-zero winding 三角化和半透明填充；自交区域 MUST 融合为一个填充区域，虚线 MUST 只绘制融合后的外轮廓而不得保留内部交错边。Subtract MUST 使用红色填充，Set 与 Add MUST 使用灰色填充。

#### Scenario: Overlay persists until release
- **WHEN** 用户继续拖动 Brush 且尚未释放左键
- **THEN** Viewport Overlay 以当前 Mode 的填充和虚线边界显示从起点到当前点的准确 footprint，Image 本身保持不变

#### Scenario: Crossing strokes merge visually
- **WHEN** Brush footprint 与自身交错或重叠
- **THEN** 交错部分显示为连续的一整块填充，虚线只围绕融合区域的外边界

### Requirement: Polyline edits Alpha through the Mask pipeline
Polyline SHALL 以逐点单击构建闭合 Selection：鼠标移动 MUST 预览下一条边；至少三个点后点击起点 8 px 范围或按 Enter MUST 完成；Backspace MUST 删除最后一个已提交点；RMB 或 Esc MUST 取消。完成的 Polyline MUST 栅格化为一个 SelectionMask，并 MUST 以当前 Set、Add 或 Subtract Mode 修改当前 Alpha，保持 RGB、图片尺寸和 Image Empty 画框不变。

#### Scenario: Clicking the start closes Polyline
- **WHEN** 用户已提交至少三个点并在起点 8 px 范围内单击
- **THEN** 系统闭合路径并应用当前 Mask Mode

#### Scenario: Enter confirms Polyline
- **WHEN** 用户已提交至少三个点并按 Enter 或 Numpad Enter
- **THEN** 系统闭合路径并应用当前 Mask Mode

#### Scenario: Backspace removes one point
- **WHEN** Polyline 已有两个以上已提交点且用户按 Backspace
- **THEN** 系统删除最后一点并继续预览未完成路径

### Requirement: Image selections carry only positive path geometry
`SelectionPath` SHALL 只保存并序列化 Points。Mask、Cutout、Scene Property、Operator 参数和 Server Job 请求 MUST NOT 声明或传递 Invert、Keep Original、Refine Selection 或 Refine Model 状态；Selection 栅格化 SHALL 只建立带抗锯齿 Padding 的局部 Path Bounds。

#### Scenario: Cutout serializes a path
- **WHEN** Cutout 把 Lasso SelectionPath 传给 Shape Operator
- **THEN** JSON 只包含 `points`，恢复后得到相同的正向路径

#### Scenario: Public state contains current concepts
- **WHEN** 系统枚举 Scene Property、Mask/Cutout Operator annotation 和 Cutout Job 请求
- **THEN** 只出现当前 Gesture、Mode、Radius、Shape、Depth 与 Normal 业务字段

