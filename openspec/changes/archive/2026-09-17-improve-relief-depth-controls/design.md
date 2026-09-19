## Context

`O Image Relief Plane` 先由 `O Image Plane` 生成固定底面位于 `Z=0`、可变面位于 `Z=Thickness` 的几何，再按 `Reference Depth - sampled depth` 计算位移。当前有厚度时，负位移最多接近 `-Thickness`，因此可变面会进入基础厚度区域；`Reference Depth` 又是校准值，不适合作为艺术调整用的整体平移控件。

## Goals / Non-Goals

**Goals:**

- 将 `Z=Thickness` 明确定义为 depth 0 和浮雕深度的最低高度。
- 让 `Depth Scale` 以 depth 0 为位移基准改变起伏幅度。
- 提供默认值为 `1` 的 `Depth Offset`，在方向换算和缩放之前进一步矫正 `Reference Depth`。
- 保持固定底面不动，并保持侧壁各层按原有权重插值位移。
- 创建 Relief Plane 时给出基于完整有效深度场的近似 `Depth Direction`。

**Non-Goals:**

- 不改变 `Reference Depth`、`Uniform Scale` 或 `Depth Direction` 的含义。
- 不改变 Depth Plane、Cutout、AI 产物及对象创建流程。
- 不为旧节点图保留兼容接口或迁移节点。

## Decisions

### 使用单一最终位移公式

可变面的完整标量位移定义为：

`corrected_reference_depth = reference_depth + depth_offset`

`relief_offset = max((direction_adjusted(corrected_reference_depth) - sampled_metric_depth) * depth_scale, 0)`

最终可变面高度为 `Thickness + relief_offset`。`Depth Offset` 与 `Reference Depth` 先相加，矫正后的参考深度再参与 `Depth Direction` 的参考平面换算、采样深度求差和 `Depth Scale` 缩放。缩放只产生从 `Thickness` 高度出发的位移，所以 depth 0 始终对应 `Thickness` 高度。

备选方案是把 `Depth Offset` 作为缩放后的几何平移，但这会脱离参考深度标定，并使 `Depth Scale=0` 时仍产生位移。将它作为 Reference Depth 矫正值，可让两者遵循同一套方向和缩放语义。

### Depth Offset 使用主界面距离输入

新增 `Depth Offset`，类型为 Float、subtype 为 `DISTANCE`、默认值为 `1`，允许正负值。`Depth Direction` 与 `Depth Offset` 均不放入 Options，主界面在 `Thickness` 后依次排列 `Depth Direction`、`Depth Offset`、`Depth Scale`。节点图先将 Depth Offset 与 `Reference Depth` 相加，再把结果传入现有 `reference_plane_depth()`。

### 沿现有层权重应用最终位移

最终 `relief_offset` 继续乘以从固定底面到可变面的 `layer_weight`。这样固定底面保持 `Z=0`，可变面应用完整位移，侧壁中间层保持线性插值。`Thickness=0` 时沿用现有权重为 `1` 的单面行为。

### Relief 与 Cutout Symmetry 共用稳健平面拟合

将稳健深度平面拟合下沉到 `common.depth`。Relief 创建时把完整深度图的有效像素中心映射到图片平面的局部 XY，以 `Uniform Scale` 转为本地深度后拟合平面，并用归一化 `(slope_x, slope_y, 1)` 初始化 `Depth Direction`。Cutout Symmetry 改用同一公共函数，继续在其裁切网格采样域上拟合，避免维护两套算法。`Depth Offset` 使用节点组默认值 `1`。

## Risks / Trade-offs

- [已有场景依赖浮雕压入基础厚度] → 这是本次明确要求的行为变化；通过几何求值测试锁定新边界，不增加兼容分支。
- [负 Depth Offset 使更多采样在 depth 0 处被截断，局部细节可能变平] → 接口说明明确 Depth Offset 是参考深度矫正，并用正、负 Depth Offset 场景覆盖预期。
- [节点接口和发布资产不一致] → 修改构建脚本后运行 `uv run node-group build`，同时检查保存资产接口和求值结果。
- [整图内容不是单一平面] → 沿用 Cutout Symmetry 的迭代稳健权重降低离群深度影响，只把结果作为可继续手调的初始值。
