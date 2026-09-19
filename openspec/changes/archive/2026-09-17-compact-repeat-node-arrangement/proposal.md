## Why

Repeat 为取值支线预留宽度，导致单个 Set Position 的循环被拉长，前置循环的处理顺序也难以辨认。

## What Changes

- 按循环执行主链排列 Repeat 两端，取值支线独立排列。
- 几何处理节点按真实上游依赖确定先后位置。
- 更新排列测试、节点资产和交互预览。
- 将长计算链紧凑排列，为复杂支线添加 Frame，并分离几何引用线通道。

## Capabilities

### New Capabilities

- `compact-repeat-arrangement`: 紧凑呈现循环执行主链并保持几何处理顺序。

### Modified Capabilities

## Impact

涉及 `tools/nodes/arrangement`、`tools/nodes/preview`、相关测试和 `O_AnyImage.blend`。
