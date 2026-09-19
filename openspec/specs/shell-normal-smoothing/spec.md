# shell-normal-smoothing Specification

## Purpose
TBD - created by archiving change compose-depth-cutout-symmetry. Update Purpose after archive.
## Requirements
### Requirement: 薄壳法线平滑不受相对厚度衰减

Shell 的 Normal Smooth SHALL 控制原正面点域法线的模糊次数，归一化后的结果用于壳体厚度偏移方向。系统 SHALL 不使用 Shell Thickness / Reference Depth 衰减该平滑；厚度控制偏移距离，Balloon 保留现有权重行为。

#### Scenario: 小厚度下调节平滑
- **WHEN** 非平面且法线有起伏的正面以小厚度生成 Shell，用户增大 Normal Smooth
- **THEN** 壳体的归一化偏移方向发生相应平滑变化，且不会因厚度与参考深度的比值接近零而退回原始法线
- **AND** 保持前表面相同而改变厚度时，平滑方向保持一致、偏移距离随厚度变化

### Requirement: 法线平滑保留正面与零厚度行为

Shell 的 Normal Smooth SHALL 仅通过厚度偏移作用于壳体，保留原深度正面；零厚度 SHALL 不因该参数改变几何。

#### Scenario: 零厚度与平面
- **WHEN** Shell 厚度为 0 时改变 Normal Smooth
- **THEN** 顶点位置与面连接保持一致
- **AND** 对常法线平面使用非零厚度时，改变 Normal Smooth 也不改变壳体形状

