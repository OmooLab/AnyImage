# cutout-boundary-smoothing Specification

## Purpose
TBD - created by archiving change weight-cutout-boundary-smoothing. Update Purpose after archive.
## Requirements
### Requirement: Boundary-specific smoothing strength

`O Image Depth Cutout` SHALL 使用单个 `Boundary Smooth` 输入控制边界平滑次数。Split 边 SHALL 使用完整 `Smooth Weight`，原始 Outline SHALL 使用 `0.1` 倍 `Smooth Weight`；两类影响相交时 Split 强度 MUST 优先。

#### Scenario: Separate Split and Outline response

- **WHEN** 同一网格同时存在 Split 边与原始 Outline 且启用 Boundary Smooth
- **THEN** Split 边按完整 Smooth Weight 平滑
- **AND** 仅受 Outline 影响的点按其 0.1 倍平滑

#### Scenario: Split and Outline intersection

- **WHEN** Split 与 Outline 的两圈影响范围相交
- **THEN** 相交区域使用两者中较强的 Split influence

### Requirement: Boundary Smooth default and bypass

`O Image Depth Cutout` 的 `Boundary Smooth` SHALL 默认为 `4`，保持范围 `0–16`；值为 `0` 时 MUST 完全旁路边界平滑。

#### Scenario: New node group defaults

- **WHEN** 构建新的 O Image Depth Cutout 节点组
- **THEN** Boundary Smooth 默认值为 4

#### Scenario: Disabled boundary smoothing

- **WHEN** Boundary Smooth 为 0
- **THEN** Split 边和 Outline 均不发生边界平滑位移

