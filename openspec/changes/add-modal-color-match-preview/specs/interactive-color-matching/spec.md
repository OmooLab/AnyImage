## ADDED Requirements

### Requirement: Color matching uses a two-axis modal interaction
系统 SHALL 在用户执行 `Match Color Reference` 后进入二维鼠标 Modal，水平控制整体 Match 强度，垂直控制低频亮度 Contrast。初始值 MUST 为 Match 100% 与 Contrast 0%，Match MUST 限制在 0%–150%，Contrast MUST 限制在 -50%–+50%，且 MUST NOT 将数值保存为 Scene 或 Operator 的持久调节属性。

#### Scenario: User adjusts the match
- **WHEN** 用户在 Modal 中水平和垂直移动鼠标
- **THEN** 系统更新 Match 与 Contrast，并在当前区域显示数值

#### Scenario: User makes a precise adjustment
- **WHEN** 用户按住 Shift 移动鼠标
- **THEN** 系统以较低灵敏度更新两个数值

### Requirement: Modal interaction uses a proxy preview
系统 SHALL 使用保持目标宽高比且最长边不超过 512 px 的独立临时 Image 显示交互预览。预览 SHALL 使用与最终处理相同的主要亮度和色度变换，但 MAY 省略最终抖动与精细色域压缩，并 SHALL 限制刷新频率以保持界面响应。

#### Scenario: User moves the mouse repeatedly
- **WHEN** Modal 收到连续鼠标移动事件
- **THEN** 系统仅更新代理预览且不修改正式目标 Image 像素

#### Scenario: A large target is previewed
- **WHEN** 目标任一边超过 512 px
- **THEN** 临时预览最长边为 512 px 且宽高比与目标一致

### Requirement: Confirmation performs one full-resolution commit
系统 SHALL 在用户左键单击或按 Enter 时恢复原始预览绑定，以当前 Match 与 Contrast 参数执行一次完整全分辨率处理，并通过现有图片编辑事务提交为一次 Undo。

#### Scenario: User confirms the preview
- **WHEN** 用户左键单击或按 Enter
- **THEN** 当前目标收到全分辨率结果，临时资源被清理，操作可由一次 Undo 恢复

### Requirement: Cancellation restores all original state
系统 SHALL 在用户右键单击或按 Esc 时恢复原始 Image、节点和材质绑定，删除本次 Modal 创建的临时 Image 与临时材质，并保持颜色参考和正式目标内容不变。

#### Scenario: User cancels the preview
- **WHEN** 用户右键单击或按 Esc
- **THEN** 原始目标绑定与内容恢复且不存在本次预览的临时数据块

#### Scenario: Target changes during the modal
- **WHEN** 目标绑定在 Modal 期间不再属于本次预览事务
- **THEN** 系统安全取消且不覆盖外部变更

### Requirement: Interactive controls preserve color matching semantics
系统 SHALL 将 Match 应用于当前目标 Image 的既有亮度和色度迁移量，并以匹配后的中间亮度为支点将 Contrast 应用于低频亮度跨度。系统 MUST 保持目标尺寸与 Alpha，继续对全部目标 RGB 生效，并 MUST NOT 引入背景检测、AI 环境或模型依赖。

#### Scenario: Contrast is increased
- **WHEN** Contrast 大于 0%
- **THEN** 亮区与暗区的低频亮度跨度增加且目标 Alpha 不变

#### Scenario: Final result is generated without AI
- **WHEN** 用户确认匹配且 AI 环境不可用
- **THEN** 系统仍在本地完成全分辨率提交

#### Scenario: A matched image is matched again
- **WHEN** 用户对已完成颜色匹配的 Image 再次执行匹配
- **THEN** 系统使用当前像素继续处理且不创建持久原图备份

#### Scenario: A matched image becomes the reference
- **WHEN** 用户从已完成颜色匹配的 Image 执行 `Set Color Reference`
- **THEN** Scene 颜色参考指向当前 Image
