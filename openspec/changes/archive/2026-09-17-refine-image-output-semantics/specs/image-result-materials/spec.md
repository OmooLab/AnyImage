## ADDED Requirements

### Requirement: Image color drives generated material IOR Level
系统 SHALL 将 Plane、Depth Plane 与 Cutout 的非 Shadeless 生成材质中 `O Image Layer` 的 Color 输出直接连接到 Principled BSDF 的 IOR Level，同时保留既有 IOR、Base Color、Roughness、Alpha、Normal 与 Displacement 连接。

#### Scenario: Dark image content suppresses highlights
- **WHEN** 生成材质采样到黑色或暗色图片内容
- **THEN** Principled BSDF 的 IOR Level SHALL 接收对应的低颜色值，从而降低该区域的高亮

#### Scenario: Bright image content preserves direct color response
- **WHEN** 生成材质采样到白色或亮色图片内容
- **THEN** Principled BSDF 的 IOR Level SHALL 接收 `O Image Layer` Color 的直接转换值，不经过额外缩放或固定上限

#### Scenario: Generated material keeps its IOR value
- **WHEN** Cutout 或 Depth Plane 以 IOR `1.2` 创建材质
- **THEN** 系统 SHALL 保留 IOR `1.2`，并由 Color 独立驱动 IOR Level
