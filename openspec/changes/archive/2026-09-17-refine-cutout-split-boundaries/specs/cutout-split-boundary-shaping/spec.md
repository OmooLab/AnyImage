## ADDED Requirements

### Requirement: Split boundary triangle cleanup

Depth Cutout SHALL 在 Split 后、投影与边界平滑前，一次删除三个顶点均在当前边界上的三角面。

#### Scenario: Remove a boundary ear
- **WHEN** Split 输出包含三个边界顶点的三角面及包含内部顶点的相邻三角面
- **THEN** 前者被删除，后者保留，清理不递归传播

### Requirement: Boundary smoothing after cleanup

Depth Cutout SHALL 在三角面清理后的几何上沿用现有 Boundary Smooth，保留其参数语义。

#### Scenario: Smooth the cleaned boundary
- **WHEN** 全边界三角面清理完成且 Boundary Smooth 大于 0
- **THEN** 现有平滑在保留几何上求值，已删除三角面不参与平滑

#### Scenario: Disable boundary smoothing
- **WHEN** Boundary Smooth 为 0
- **THEN** 深度及网格平滑步骤保持各自输入值，其他切口形状处理继续按当前参数求值

### Requirement: Rounded split thickness profile

Depth Cutout SHALL 使新切口的 Balloon 厚度轮廓在边界为零，在邻近区域连续恢复，并使 Edge Round 影响新切口的圆润过渡。

#### Scenario: Form a new meeting boundary
- **WHEN** Split 产生内部切口并执行 Balloon 厚度成形
- **THEN** 新切口前后表面在零厚度边界交汇，影响带外保留原厚度轮廓

#### Scenario: Adjust edge rounding
- **WHEN** 用户增加 Edge Round
- **THEN** 新切口的过渡带随之加宽，最终几何呈现圆润过渡的变化，原 Alpha 轮廓继续使用既有规则

#### Scenario: No new boundary
- **WHEN** 当前 Split 结果没有新增边界
- **THEN** 切口轮廓步骤保留原厚度字段

### Requirement: Thickness weighted normal smoothing

Depth Cutout SHALL 始终按归一化厚度的 smoothstep 权重混合原法向与平滑法向，再归一化；保留 Normal Smooth 对平滑迭代数的控制。

#### Scenario: Thin thickness
- **WHEN** Balloon Thickness 趋于 0，或 Uniform Thickness 与 Reference Depth 的比例趋于 0
- **THEN** 法向平滑引入的方向偏差连续趋于 0，结果保持有限

#### Scenario: Full smoothing strength
- **WHEN** 归一化厚度达到或超过 1
- **THEN** 使用完整的既有法向平滑结果

#### Scenario: Normal smoothing disabled
- **WHEN** Normal Smooth 为 0
- **THEN** 混合结果等于对应消费几何上的原法向归一化结果

### Requirement: Live cutout controls

Depth Cutout SHALL 在每次参数变更后重新求值 Split、边界平滑和厚度成形，保留现有参数接口。

#### Scenario: Edit the loaded modifier
- **WHEN** 用户加载节点资产后连续修改 Split Threshold、Boundary Smooth 和 Edge Round
- **THEN** 几何按新参数实时更新，恢复相同参数可重现相同结果，不依赖冻结的中间网格

### Requirement: Loadable node asset

本功能 SHALL 随正式节点资产交付，所有相关节点组及测试辅助图保持 Capture Attribute 为零，并保留用户属性。

#### Scenario: Independently load built asset
- **WHEN** 在独立 Blender 进程加载重建资产
- **THEN** 接口、动态形状求值和必要属性均正确，输出不含实验诊断或已结束生命周期的内部临时属性
