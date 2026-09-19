## Context

`O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` 共用 `common/boundary_smoothing.py` 的 `smooth_cut_boundary()`，最终调用 `common/smoothing.py` 的 `expand_smooth()`。`expand_smooth()` 目前支持 `weight_name`、`pin_sharp` 与无影响场三种形态，但边界平滑只使用「影响场 + 固定权重」这一种。三个节点组把该权重公开为 `Smooth Weight`，默认值始终为 1。

Options 面板当前的 `Reference Depth` 排在首位，而该值是服务端标定结果，只有更换深度尺度时才需要手工调整。

## Goals / Non-Goals

**Goals:**

- 三个深度节点组不再公开 `Smooth Weight`，边界平滑保持默认强度下的现有结果。
- `expand_smooth()` 只保留实际使用的调用形态。
- 深度与浮雕节点组的 Options 中 `Reference Depth` 位于最后一项。

**Non-Goals:**

- 不改变边界平滑的影响带宽度、迭代次数、保护规则和轮廓权重。
- 不改变 `Reference Depth` 的几何含义、初始化来源与取值范围。
- 不为已保存的 `Smooth Weight` 值提供兼容入口。

## Decisions

### 边界平滑权重固定为 1

权重只作为位置混合系数与影响场相乘，默认值 1 意味着混合完全由影响场决定。直接删除该输入并把混合系数接到影响场，节点图少一层乘法，结果与默认参数一致。

### `expand_smooth()` 收敛为单一形态

唯一调用方传入影响场且不平滑法线，因此删除 `weight_name`、`pin_sharp` 分支与 `influence=None` 分支，签名收敛为 `expand_smooth(group, geometry, iterations_name, influence)`。相比保留未用参数，直接删除可避免后续再出现同类权重输入。

### `Reference Depth` 放到 Options 末尾

三个组的 Options 依次为：Depth Plane `Boundary Smooth`、`Mask Threshold`、`Reference Depth`；Depth Cutout `Boundary Smooth`、`Normal Smooth`、`Front Inflation`、`Reference Depth`；Relief Plane `Mask Threshold`、`Reference Depth`。标定输入不再挤占艺术调整参数的位置。

### 测试用 `Boundary Smooth` 与影响带判断替代权重隔离

原先用 `Smooth Weight = 0` 关闭位置平滑的用例，改为 `Boundary Smooth = 0` 的直通路径，或把断言限制在影响带之外的点。

## Risks / Trade-offs

- [移除权重后无法再单独关闭位置平滑] → 位置平滑与迭代次数同属一次边界平滑，`Boundary Smooth = 0` 已是完整的关闭路径。
- [已保存场景的 Modifier 仍带 `Smooth Weight`] → 已保存数值按原样保留，该输入不再影响求值，重新生成几何时按默认强度构建。
