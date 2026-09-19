## ADDED Requirements

### Requirement: Image layer exposes alpha adjustment strength

O Image Layer SHALL 在默认折叠的 `Options` 面板中依次提供 `Alpha Fix`、`Normal Scale`、`Object Space`。Alpha Fix SHALL 为浮点输入，范围 0–1，subtype 为 FACTOR，默认 0，并以该值控制内部 Alpha Float Curve 的 Factor。

#### Scenario: Options are initially collapsed
- **WHEN** 创建 O Image Layer 节点实例
- **THEN** Options 面板 SHALL 默认折叠，包含 Alpha Fix、Normal Scale、Object Space
- **AND** Color、Alpha、Normal、Bump Scale SHALL 位于面板外

#### Scenario: Adjustment is disabled
- **WHEN** Alpha Fix 为 0
- **THEN** 组输出 Alpha SHALL 等于输入 Alpha

#### Scenario: Adjustment is fully applied
- **WHEN** Alpha Fix 为 1
- **THEN** 组输出 Alpha SHALL 等于内部 Float Curve 对输入 Alpha 的求值

#### Scenario: Adjustment is partially applied
- **WHEN** Alpha Fix 为 0.5
- **THEN** 输出 SHALL 等于原始 Alpha 与完整曲线结果的平均值

### Requirement: Alpha curve follows the reference profile

Alpha 曲线 SHALL 使用四个点：起点 `(0, 0)`、低端控制点 `(0.8, 0)`、靠近右上方的平滑控制点和终点 `(1, 1)`，形成参考图中的快速上升轮廓。对输入范围 0–1，完整调整后的输出 SHALL 保持在 0–1，保持单调不减，并保持完全透明与完全不透明端值。

#### Scenario: Low alpha is suppressed
- **WHEN** 输入 Alpha 在 0–0.8 且调整强度为 1
- **THEN** 输出 Alpha SHALL 为 0，允许浮点求值误差

#### Scenario: Opaque alpha is preserved
- **WHEN** 输入 Alpha 为 1
- **THEN** 任意调整强度下输出 Alpha SHALL 为 1

### Requirement: Material creation initializes adjustment from preferences

创建使用 O Image Layer 的材质时，系统 SHALL 通过现有偏好读取入口，将 Alpha Fix 初始化为 `Adapt to Scene View Transform` 开启时的 1、关闭时的 0。

#### Scenario: Adaptation is enabled
- **WHEN** 开启适配后创建普通着色或 Shadeless 材质
- **THEN** O Image Layer 实例的 Alpha Fix SHALL 为 1
- **AND** 对应着色器 SHALL 使用该组调整后的 Alpha 输出

#### Scenario: Adaptation is disabled
- **WHEN** 关闭适配后创建材质
- **THEN** O Image Layer 实例的 Alpha Fix SHALL 为 0

#### Scenario: Color space falls back
- **WHEN** 适配开启且颜色空间解析回退到 sRGB
- **THEN** 新建 O Image Layer 实例的 Alpha Fix SHALL 仍为 1

#### Scenario: Existing material is manually adjusted
- **WHEN** 用户修改现有材质的 Alpha Fix 后切换偏好
- **THEN** 已有实例的调整值 SHALL 保留
- **AND** 后续新建材质 SHALL 使用当前偏好初始化
