## ADDED Requirements

### Requirement: Color matching uses an adaptive spatial color signature
系统 SHALL 从参考与目标的受限尺寸代理中提取确定性的空间显著颜色签名。签名 SHALL 综合颜色面积、颜色独特性、邻域对比和空间连通性，并 SHALL 根据加权颜色重建误差自动保留 8–16 个迁移锚点。色度迁移 SHALL 支持参考与目标使用不同数量的锚点，且 Lightness 迁移 SHALL 保持独立。

#### Scenario: A small coherent accent contrasts with its surroundings
- **WHEN** 参考图包含面积较小、空间连续且与邻域明显不同的颜色区域
- **THEN** 该颜色能够获得有效签名权重并参与目标色度迁移，而不被大面积近似背景色完全掩盖

#### Scenario: A small saturated accent appears in a muted image
- **WHEN** 参考图包含面积较小但高色度、空间连续且边界清晰的颜色区域
- **THEN** 面积权重不会单独排除该颜色，签名使用该色簇中较高色度的真实像素表示它

#### Scenario: Reference and target have different color complexity
- **WHEN** 参考与目标根据重建误差选择了不同数量的迁移锚点
- **THEN** 系统使用权重守恒的不等长签名完成平滑色度迁移

#### Scenario: An image has a simple color distribution
- **WHEN** 8 个锚点已足以将加权色度重建误差降至内部阈值
- **THEN** 系统停止增加锚点，且不为该图片固定扩展到 16 或 24 个

#### Scenario: An image has a complex color distribution
- **WHEN** 较少锚点不能满足加权色度重建误差阈值
- **THEN** 系统增加迁移锚点但不超过 16 个
