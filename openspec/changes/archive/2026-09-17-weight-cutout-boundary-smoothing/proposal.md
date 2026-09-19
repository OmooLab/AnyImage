## Why

`O Image Depth Cutout` 的 Split 边与原始 Outline 对几何平滑的需求不同：Split 边需要完整强度消除切缝折痕，而 Outline 只需轻微整理，避免轮廓被过度软化。

## What Changes

- `Boundary Smooth` 继续作为唯一的边界平滑次数控制，默认值改为 `4`。
- Split 边使用完整 `Smooth Weight`，Outline 使用其 `0.1` 倍；两类影响相交时由 Split 强度优先。
- 保持 `Boundary Smooth = 0` 完全关闭边界平滑。

## Capabilities

### New Capabilities

- `cutout-boundary-smoothing`: 定义 Depth Cutout 对 Split 边与 Outline 的差异化平滑强度和默认控制值。

### Modified Capabilities

无。

## Impact

影响 `tools/nodes/common/boundary_smoothing.py`、`tools/nodes/groups/image_depth_cutout.py`、相关节点测试和 `src/anyimage/assets/O_AnyImage.blend`；不增加或移除公开输入。
