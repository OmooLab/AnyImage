## ADDED Requirements

### Requirement: Geometry depth groups expose Reference Depth
系统 SHALL 在 `O Image Depth Plane`、`O Image Cutout`、Depth Balloon 与 Depth Surface 的 Geometry Nodes 接口中使用 `Reference Depth` 表示深度纹理的参考距离，并且 MUST 不再公开 `Base Plane Depth`。

#### Scenario: Depth Plane initializes its reference
- **WHEN** 系统根据 `depth.json` 创建 Depth Plane Modifier
- **THEN** `reference_depth × uniform_scale` SHALL 写入 `Reference Depth`

#### Scenario: Depth Cutout initializes its reference
- **WHEN** 系统根据最终网格内容标定 Depth Balloon 或 Depth Surface
- **THEN** 标定结果 SHALL 写入主 Cutout 与对应子组的 `Reference Depth`

#### Scenario: Node asset exposes the current interface only
- **WHEN** 系统构建并验证 `O_AnyImage.blend`
- **THEN** 所有相关节点组、面板、依赖连线和 Modifier 输入 SHALL 只包含 `Reference Depth`，不得保留旧名称或兼容 socket

### Requirement: Reference Depth keeps existing geometry meaning
`Reference Depth` SHALL 继续作为采样 Depth 的运算基准，不改变 Depth Plane、Depth Balloon 或 Depth Surface 的几何方向、尺度、厚度和位移公式。

#### Scenario: Reference control changes relative depth
- **WHEN** 用户修改 `Reference Depth`
- **THEN** Geometry Nodes SHALL 使用 `Reference Depth - sampled depth` 的既有相对深度关系更新几何
