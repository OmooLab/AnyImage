## Context

Depth Cutout 当前在 Split 后对全部实际边界使用同一两圈 influence 和同一 `Smooth Weight`。原始 Outline 需要保形，Split 形成的切边则需要更强平滑；两者可通过分裂前原始几何的轮廓字段区分。

## Goals / Non-Goals

**Goals:**

- 只保留一个 `Boundary Smooth` 次数输入。
- Split 边使用完整强度，Outline 使用固定 `0.1` 倍强度。
- 两类影响带相交时保留更强的 Split 平滑。

**Non-Goals:**

- 不增加独立的 Outline 或 Split 平滑参数。
- 不改变影响带宽度、整体 `Smooth Weight` 或普通 `Smooth` 的语义。

## Decisions

在 Split 前保留原始几何引用，并在当前投影几何上通过 `original_boundary_field()` 识别原始 Outline。分别构造 Outline 与 Split 边界字段及其两圈 influence：当前实际边界扣除 Outline 后作为 Split 边，Outline influence 乘 `0.1`，最终使用两者最大值。

两类边界继续进入同一个 Repeat Zone，共用 `Boundary Smooth` 次数和 `Smooth Weight`。相比串联两套平滑循环，这样不会增加公开参数，并保持节点数量与求值成本较低。交汇区域取最大值，使 Split 的完整强度优先。

`Boundary Smooth` 默认值改为 `4`，范围及零值旁路保持不变。

## Risks / Trade-offs

- Outline 每轮权重为 `0.1`，多次迭代后的累计位移不等于最终位移的 10% → 以行为测试验证它始终弱于相同设置下的 Split，并由默认 4 次控制累计程度。
- Split influence 向 Outline 邻域扩散时会在交点附近覆盖弱 Outline influence → 这是 Split 优先规则的预期结果，测试交汇区域输出有限且拓扑不变。
