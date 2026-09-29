## ADDED Requirements

### Requirement: Material image textures expose color reference actions
系统 SHALL 在材质 Shader Editor 中为具有有效静态 Image 的活动 Image Texture 提供 `Set Color Reference` 与 `Match Color Reference`，并 SHALL 仅使用当前编辑树中的活动节点图片。

#### Scenario: A static image texture is active
- **WHEN** 用户在材质编辑上下文中打开有效静态 Image Texture 的 `AnyImage` 菜单
- **THEN** 菜单显示 `Set Color Reference`，并在当前 Scene 存在另一有效参考时启用 `Match Color Reference`

#### Scenario: The editor target is unavailable
- **WHEN** 当前上下文不是材质 Shader Editor，或活动节点没有有效静态 Image
- **THEN** 两项颜色参考操作不可执行，且不使用活动对象或 Image Empty 作为替代目标

#### Scenario: Node selection changes after matching starts
- **WHEN** 颜色匹配处理期间用户切换编辑器、材质或活动节点
- **THEN** 结果仍提交到发起操作时捕获的节点；原节点失效时拒绝提交并清理结果
