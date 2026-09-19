## Why

Cutout 目前只能自由绘制 Lasso，沿直线轮廓剪出时需要逐点定义边界。复用 Mask 的 Polyline 交互，并为这种剪出方式设置 Uniform 厚度，可减少手动调整；Mask 使用 Extend 和默认 Set，使名称与常用操作一致。

## What Changes

- Cutout 增加 Gesture 选项 Lasso / Polyline，默认 Lasso，复用共用逐点交互和选区提交链路。
- Polyline 剪出创建使用 `O Image Depth Cutout` 的 Depth Solid 对象时，自动设置修改器 Mode 为 Uniform。
- `O Image Depth Cutout` 的 Uniform Thickness 接口默认值改为 0.5（资产中显示为 Thickness）。
- **BREAKING** Mask 的 `ADD` / Add 统一重命名为 `EXTEND` / Extend，保留扩展 Alpha 的运算语义；默认模式从 Subtract 改为 Set。

## Capabilities

### New Capabilities

- `cutout-polyline`: Cutout 手势选择、共用 Polyline 交互，以及创建结果的 Uniform 初始化。
- `mask-mode-options`: Mask 的 Set / Extend / Subtract 名称、运算和默认值。

### Modified Capabilities

无。当前 `openspec/specs` 尚无已归档的对应规范。

## Impact

- `properties.py`、`common/viewport.py`、`operators/cutout_tool`、`operators/mask_tool.py` 和相关注册、交互、对象创建测试。
- `tools/nodes/groups/image_depth_cutout.py`、节点资产 `O_AnyImage.blend` 及节点测试；实现阶段需运行节点构建与验证。
- 无新增依赖。已有 change 中的 Mask、Polyline 和 Cutout 提案作为实现背景，本 change 定义本次行为。
