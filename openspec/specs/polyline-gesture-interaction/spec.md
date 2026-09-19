# polyline-gesture-interaction Specification

## Purpose
TBD - created by archiving change match-polyline-gesture-interaction. Update Purpose after archive.
## Requirements
### Requirement: Polyline exposes a progressive close target
Polyline SHALL 在至少三个已提交点后，根据鼠标到起点的屏幕距离显示渐进闭合提示。实际闭合半径 MUST 为 `15 px × UI Scale`；提示距离 MUST 为实际闭合半径的平方。鼠标从提示范围边缘接近起点时，提示圈半径 MUST 通过平滑插值从 `1 px × UI Scale` 增长到实际闭合半径，并 MUST 使用明暗对比轮廓保持可见。

#### Scenario: Cursor approaches the start point
- **WHEN** Polyline 已提交至少三个点，且鼠标从提示范围边缘向起点移动
- **THEN** 起点提示圈连续放大，并在鼠标到达起点时显示为实际闭合半径

#### Scenario: Cursor remains outside the hint distance
- **WHEN** Polyline 已提交至少三个点，但鼠标位于提示距离之外
- **THEN** 系统不绘制起点闭合提示圈

#### Scenario: Polyline has fewer than three points
- **WHEN** Polyline 尚未提交三个点
- **THEN** 系统不绘制起点闭合提示圈且不允许点击起点完成

#### Scenario: UI Scale changes
- **WHEN** Blender UI Scale 不是 1.0
- **THEN** 闭合命中半径、提示距离与提示圈尺寸使用同一 UI Scale 计算

### Requirement: Polyline supports deliberate mouse completion
Polyline SHALL 在至少三个已提交点后允许用户点击起点实际闭合半径内或双击左键完成。起点点击 MUST 不添加新顶点；双击的第二击 MUST 不添加重复顶点。点数不足时，点击或双击 MUST NOT 提交 Selection。

#### Scenario: User clicks inside the close target
- **WHEN** Polyline 已提交至少三个点，且用户在起点实际闭合半径内按下左键
- **THEN** 系统使用现有已提交顶点完成 Polyline，不添加点击位置为新顶点

#### Scenario: User double-clicks after three points
- **WHEN** Polyline 已提交至少三个点，且用户双击左键
- **THEN** 系统完成 Polyline，并且双击的第二击不产生重复顶点

#### Scenario: User double-clicks before three points
- **WHEN** Polyline 的已提交点少于三个，且用户双击左键
- **THEN** 系统保持 Polyline Modal 运行且不提交 Selection

#### Scenario: User clicks outside the close target
- **WHEN** Polyline 已提交至少三个点，且用户在起点实际闭合半径外单击有效的新位置
- **THEN** 系统提交该位置为下一个顶点并继续 Polyline

### Requirement: Polyline retains keyboard and cancellation controls
Polyline MUST 保留 Enter 与 Numpad Enter 完成、Backspace 删除最后一点、RMB 与 Esc 取消以及工具切换取消的现有行为。状态文本 SHALL 同时说明点击起点、双击或 Enter 可以完成，并说明 Backspace 删除一点。

#### Scenario: User confirms with Enter
- **WHEN** Polyline 已提交至少三个点，且用户按 Enter 或 Numpad Enter
- **THEN** 系统完成 Polyline

#### Scenario: User removes the last point
- **WHEN** Polyline 已提交两个或更多点，且用户按 Backspace
- **THEN** 系统删除最后一个已提交点并继续预览

#### Scenario: User cancels the gesture
- **WHEN** 用户按 RMB、Esc 或切换到其他工具
- **THEN** 系统取消未完成的 Polyline 并移除 Overlay

### Requirement: Mask uses a cross painting cursor
Mask Tool SHALL 为 Lasso、Brush 与 Polyline Gesture 统一使用 Blender 的 `PAINT_CROSS` cursor。

#### Scenario: User activates Mask
- **WHEN** 用户在 3D Viewport 激活 Mask Tool
- **THEN** 工具光标显示为 `PAINT_CROSS`，并在切换 Lasso、Brush 与 Polyline 时保持一致

