# mask-mode-options Specification

## Purpose
TBD - created by archiving change add-cutout-polyline. Update Purpose after archive.
## Requirements
### Requirement: Mask exposes Set Extend and Subtract

Mask MUST 按顺序提供 `SET` / Set、`EXTEND` / Extend、`SUBTRACT` / Subtract，枚举数值分别为 0、1、2；界面和状态文本 MUST 使用 Extend。

#### Scenario: User extends Alpha
- **WHEN** 用户以 Extend 提交值为 mask 的选区到现有 alpha
- **THEN** 结果 Alpha 为 `max(alpha, mask)`，RGB 保持不变

#### Scenario: User uses Set or Subtract
- **WHEN** 用户使用 Set 或 Subtract
- **THEN** 结果 Alpha 分别为 `alpha * mask` 或 `alpha * (1-mask)`，RGB 保持不变

### Requirement: Mask defaults to Set

Scene 的 Mask Mode 和 Mask Operator 的模式属性 MUST 默认 Set，并通过同一属性定义保持一致。

#### Scenario: New scene and operator defaults
- **WHEN** 创建新 Scene 或未指定模式的 Mask Operator
- **THEN** 模式默认值为 `SET`

#### Scenario: User chooses another mode
- **WHEN** 用户主动设置 Extend 或 Subtract 后启动 Mask
- **THEN** 本次操作使用用户保存的模式

