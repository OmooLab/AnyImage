## MODIFIED Requirements

### Requirement: Color Match Panel explains the reference palette
系统 SHALL 在参考画廊下显示由当前参考迁移签名折叠得到的动态色板，并 SHALL 在 Color Reference 改变时根据参考图可见像素更新。当迁移签名至少包含三个锚点时，色板 SHALL 合并感知上接近的迁移锚点并显示 3–7 个有效色块；退化的少色参考 SHALL 仅显示其实际颜色。色板 SHALL 以色块宽度表达合并权重，使用色簇内较高色度的真实代表色，并 MUST NOT 使用 Blender 的禁用灰化状态。色板 MUST 忽略完全透明像素，并 MUST 仅作为完整迁移签名的折叠说明，不得将最终匹配限制为可见色块数量。

#### Scenario: A reference with several distinct color families is selected
- **WHEN** 用户选择具有可见像素且包含多个显著颜色族的 Color Reference
- **THEN** Panel 显示三至七个动态宽度、未灰化的色块，且每个色块来自实际参与迁移的锚点

#### Scenario: Similar anchors are present
- **WHEN** 多个迁移锚点只有细微感知差异
- **THEN** Panel 将其合并为一个代表色块并合并其迁移权重，但不会将正常签名压缩到三块以下，且保留该颜色族中较高色度的真实代表色

#### Scenario: The reference is cleared
- **WHEN** 用户清空 Color Reference
- **THEN** Panel 清空色板数量、颜色和权重，且不保留上一张参考的显示值
