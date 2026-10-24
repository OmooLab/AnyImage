## ADDED Requirements

### Requirement: Color matching uses a two-axis modal interaction
系统 SHALL 在用户执行 `Match Color Reference` 后进入二维鼠标 Modal，水平控制 Color 迁移强度，垂直控制 Lightness 迁移强度。两者初始值 MUST 均为 50%，范围 MUST 均限制在 0%–100%，且 MUST NOT 将数值保存为 Scene 或 Operator 的持久调节属性。

#### Scenario: User adjusts the match
- **WHEN** 用户在 Modal 中水平和垂直移动鼠标
- **THEN** 系统更新 Color 与 Lightness，并在视口中央预览上显示数值与操作提示

#### Scenario: User makes a precise adjustment
- **WHEN** 用户按住 Shift 移动鼠标
- **THEN** 系统以较低灵敏度更新两个数值

### Requirement: Modal interaction uses a proxy preview
系统 SHALL 使用保持目标宽高比且最长边不超过 512 px 的独立临时 Image，通过当前区域的居中绘制层显示交互预览。预览 SHALL 使用与最终处理相同的主要亮度和色度变换，但 MAY 省略最终抖动与精细色域压缩，并 SHALL 限制刷新频率以保持界面响应。Modal 期间 MUST NOT 将临时 Image 绑定到目标 Owner、节点或材质。

#### Scenario: User moves the mouse repeatedly
- **WHEN** Modal 收到连续鼠标移动事件
- **THEN** 系统仅更新代理预览且不修改正式目标 Image 像素

#### Scenario: A large target is previewed
- **WHEN** 目标任一边超过 512 px
- **THEN** 临时预览最长边为 512 px 且宽高比与目标一致

### Requirement: Confirmation performs one full-resolution commit
系统 SHALL 在用户左键单击或按 Enter 时移除居中预览，以当前 Color 与 Lightness 参数执行一次完整全分辨率处理，并通过现有图片编辑事务提交为一次 Undo。

#### Scenario: User confirms the preview
- **WHEN** 用户左键单击或按 Enter
- **THEN** 当前目标收到全分辨率结果，临时资源被清理，操作可由一次 Undo 恢复

### Requirement: Cancellation restores all original state
系统 SHALL 在用户右键单击或按 Esc 时移除居中绘制层并删除本次 Modal 创建的临时 Image，保持颜色参考、正式目标内容及其 Image、节点和材质绑定不变。

#### Scenario: User cancels the preview
- **WHEN** 用户右键单击或按 Esc
- **THEN** 原始目标绑定与内容从未被预览替换，且不存在本次预览的临时数据块或绘制回调

#### Scenario: Target changes during the modal
- **WHEN** 目标绑定在 Modal 期间不再属于本次预览事务
- **THEN** 系统安全取消且不覆盖外部变更

### Requirement: Interactive controls preserve color matching semantics
系统 SHALL 将 Color 直接应用于当前目标 Image 的色度迁移量，将 Lightness 直接应用于低频亮度分位映射，并以 100% 表示完整迁移，不叠加隐藏强度或外推。参考色度统计 SHALL 忽略透明像素并适度提高有色像素权重，同时保持可见面积主导。系统 MUST 保持目标尺寸与 Alpha，继续对全部目标 RGB 生效，并 MUST NOT 引入背景检测、AI 环境或模型依赖。

#### Scenario: One dimension is disabled
- **WHEN** Color 或 Lightness 为 0%
- **THEN** 系统保留目标图对应的色度或明暗维度，另一个维度仍可独立迁移

#### Scenario: Final result is generated without AI
- **WHEN** 用户确认匹配且 AI 环境不可用
- **THEN** 系统仍在本地完成全分辨率提交

#### Scenario: A matched image is matched again
- **WHEN** 用户对已完成颜色匹配的 Image 再次执行匹配
- **THEN** 系统使用当前像素继续处理且不创建持久原图备份

#### Scenario: A matched image becomes the reference
- **WHEN** 用户从已完成颜色匹配的 Image 执行 `Set Color Reference`
- **THEN** Scene 颜色参考指向当前 Image
