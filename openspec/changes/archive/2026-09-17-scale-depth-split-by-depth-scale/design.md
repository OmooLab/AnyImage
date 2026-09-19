## Context

Depth Split 的判据在 `split_depth_surface`（`tools/nodes/common/depth_surface.py`），在边域求值，被 `O Image Depth Plane`、`O Image Depth Cutout`、`O Image Depth Panorama` 共用。当前式子是：

```
|Δ射线距离| × Reference × Strength  >  面中心距离 × 平均射线距离 × 2.5
```

四个量各有分工：Δ 是共享边两个面各自的 `|相机 XYZ|` 之差，`Reference` 把无量纲的相对跳变换算回局部长度尺度，`面中心距离` 用采样密度归一化（Subdivide 变化不改变选择），`平均射线距离` 把绝对差归一化成相对跳变（深度图整体缩放不改变选择）。Depth Scale 不在其中。

投影后的深度落差是 `Δ × Depth Scale`：`Y = (Reference − 相机 Z × Uniform Scale) × Depth Scale`。所以判据里缺的正是这个因子。

## Goals / Non-Goals

**Goals:**

- Depth Scale 为 0 时表面完全平整且不被切开、不删除条带面，输出与关闭 Split 相同。
- 判据表达投影后的几何落差，切边随 Depth Scale 单调出现。
- 默认 Depth Scale 为 1 时结果与当前实现完全一致。
- 三个共用判据的资产行为一致。

**Non-Goals:**

- 不改变相对跳变的归一化方式：平均射线距离、面中心距离、Reference 的作用保持不变。
- 不新增 Split 参数、不引入自动阈值或滞回。
- 不改变切边后顶点沿射线重新定位、条带面清理、边界平滑的既有规则。
- 不改动 `O Image Relief Plane` 与全景的球面半径插值。

## Decisions

**只把 Depth Scale 乘进落差项，不动归一化因子。** 分子就是投影后 Y 方向的真实落差，分母承担的是采样密度与深度数据整体尺度的归一化，跟显示幅度无关；分母也跟着乘会让阈值失去可解释的单位。备选是把 Depth Scale 当开关（只有 0 才禁用 Split），那样阈值不连续，中间幅度没有意义；另一个备选是在投影后的几何上重新求值判据，需要重建面中心距离与射线距离，代价大而收益只是一个常数因子的精度。

**Depth Scale 作为 `split_depth_surface` 的显式参数，由三个调用方各自传入。** 三个资产共用同一判据，参数化后行为一致，不引入全局读取或隐式约定。全景的 Depth Scale 本来就参与「球半径到预测距离」的插值，乘进判据与它的显示语义一致。

**不加平滑或滞回。** Split 是硬阈值，滞回会让同一网格的拓扑依赖求值历史，与现有单次求值模型不符。低 Depth Scale 下拖参数导致的跳变按既定语义接受。

## Risks / Trade-offs

- 拖动 Depth Scale 时会出现「突然全部切开」的跳变 → 接受。Split 本来就是阈值判断，Depth Scale 为 0 的纯净行为优先。
- Depth Scale 开始影响拓扑：顶点数、边界平滑结果、壳壁都随之变化 → 接受，并在 Depth Split 的参数说明中写清它随 Depth Scale 缩放。
- 已保存场景若 Depth Scale 小于 1，切边会比以前少 → 这是本次改动的目的；默认值 1 的场景不受影响。
- 与 `reorganize-cutout-shapes` 中「Split 独立于显示深度幅度」的条目冲突 → 在同一变更里修订该条目。
