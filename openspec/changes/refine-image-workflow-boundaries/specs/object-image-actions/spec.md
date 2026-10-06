## ADDED Requirements

### Requirement: Baked objects relinquish the image capability
系统 SHALL 在 Bake 成功后移除结果对象的 `o_image_object`，使其按普通 Mesh 参与对象目标识别。3D View 和 Outliner SHALL 依照同一标记确定 AnyImage 对象右键菜单的可用性。

#### Scenario: Bake succeeds
- **WHEN** 支持的 AnyImage 对象成功 Bake
- **THEN** 结果对象没有 `o_image_object`，对象右键菜单与对象图片 Operator 的目标识别均不可用

#### Scenario: Bake is undone and redone
- **WHEN** 用户对成功 Bake 执行 Undo 后再 Redo
- **THEN** Undo 恢复原节点栈、能力标记和对象图片操作，Redo 恢复普通 Mesh 身份

#### Scenario: Bake fails
- **WHEN** Bake 处理失败
- **THEN** 源对象仍保留原能力标记及对象图片操作行为

#### Scenario: A baked material image texture is active
- **WHEN** 用户在 Shader Editor 中选择 baked 材质的有效 Image Texture 节点
- **THEN** 贴图节点的 AnyImage 菜单和图片操作沿用现有节点上下文逻辑，与对象标记独立
