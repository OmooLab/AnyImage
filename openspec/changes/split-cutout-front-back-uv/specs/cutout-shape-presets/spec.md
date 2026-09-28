## ADDED Requirements

### Requirement: Cutout 厚度模式共享双区 UV 协议

O Image Cutout 与 O Image Depth Cutout 的 Balloon、Shell 模式 SHALL 使用同一上下双区 UV 协议。当前模式厚度为零时 SHALL 只输出上半区 Front；正厚度时 SHALL 将生成 Rear 分配到下半区，并将 Side 按 Front-side 上区、Rear-side 下区分开。

#### Scenario: 在 Balloon 与 Shell 间切换
- **WHEN** 用户在同一 Cutout 对象上分别选择 Balloon 和 Shell，并为当前模式设置正厚度
- **THEN** 两种模式的 Front、Rear、Front-side 与 Rear-side 均遵守相同 UV 区域分配
- **AND** 切换模式不需要重新生成图片、材质或对象

#### Scenario: 厚度归零再恢复
- **WHEN** 用户将当前厚度从正值调为零后再恢复为正值
- **THEN** 零厚度阶段只保留上半区 Front
- **AND** 恢复后生成的 Rear 再次使用下半区，图片和材质保持不变

#### Scenario: Flat 后续增厚
- **WHEN** 用户把初始 Flat 的 Balloon 或 Shell 厚度调为正值
- **THEN** 已有双区图片直接为新 Rear 提供下半区采样
- **AND** 无需重建材质或重新运行 AI
