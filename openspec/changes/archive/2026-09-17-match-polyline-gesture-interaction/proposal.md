## Why

当前 Polyline 只有固定 8 px 起点命中圈，闭合目标出现突然、范围偏小，并且只能点击起点或按 Enter 完成。对齐 Blender Sculpt Polyline Gesture 的渐进起点提示、双击完成和十字光标，可以让闭合意图更清楚并减少精确回点操作。

## What Changes

- 至少提交三个点后，在起点周围显示随鼠标距离平滑放大的闭合提示圈。
- 使用与 Blender Polyline Gesture 一致的 15 px 起点点击范围，并按 UI Scale 调整屏幕尺寸。
- 支持在已有有效 Polygon 时双击左键完成 Polyline，同时保留点击起点、Enter、Backspace、RMB 和 Esc 行为。
- Mask Tool 使用 `PAINT_CROSS` 光标，让 Lasso、Brush 与 Polyline 保持统一的图片区域编辑指针。
- 更新 Polyline 状态提示、交互测试和内部文档。

## Capabilities

### New Capabilities

- `polyline-gesture-interaction`: 定义 Polyline 的渐进闭合提示、起点命中、双击完成、键盘控制与工具光标。

### Modified Capabilities

## Impact

- 影响 `common/viewport.py` 的 Polyline 屏幕空间提示、命中判断和 Modal 状态机。
- 影响 `operators/image_edit_tool/mask.py` 的 Mask Tool 光标与状态文本。
- 影响 Blender Add-on 交互测试与 Image Edit Tool 内部文档。
- 不改变 SelectionPath、SelectionMask、Alpha 合成、图片尺寸、对象结构或 Server 协议，不增加依赖。
