## Purpose

为材质 Shader Editor 中的 Image Texture 节点提供直接去背景与放大的操作入口，让用户在现有节点位置使用处理结果，并明确共享图片、异步完成和撤销恢复的可见行为。

## ADDED Requirements

### Requirement: Material image texture context actions

系统 SHALL 在材质 Shader Editor 中为具有有效图片的活动 Image Texture 节点提供 AnyImage 右键菜单，包含 Remove Background 和 Upscale；一次操作 SHALL 处理当前节点。

#### Scenario: An image texture is active
- **WHEN** 用户在材质编辑上下文中对有图片的活动 Image Texture 节点打开右键菜单
- **THEN** 菜单提供两项操作，Upscale 显示预期 2× 输出尺寸

#### Scenario: The target is unavailable
- **WHEN** 当前上下文为 World、Compositor、Geometry Nodes，或活动节点不是 Image Texture、没有图片、不可编辑
- **THEN** 系统不提供可执行的节点图片操作，且不使用活动 Empty 作为替代目标

#### Scenario: A material or node group is being edited
- **WHEN** 用户固定材质或进入其节点组并对有效 Image Texture 发起操作
- **THEN** 系统处理该编辑树内的目标节点图片

### Requirement: Existing AI processing settings apply

系统 SHALL 沿用 Empty Image 操作的 AI 环境准备、模型选择、任务状态和输入限制；Upscale SHALL 使用当前模型输出 2× 结果。

#### Scenario: Environment preparation is needed
- **WHEN** 用户点击操作且 AI 环境或模型尚未准备好
- **THEN** 系统进入现有准备流程

#### Scenario: Upscale is unavailable
- **WHEN** 服务忙碌或图片长边达到当前最大 AI 输入尺寸
- **THEN** Upscale 不可执行；服务忙碌时 Remove Background 也不可执行

#### Scenario: An animated texture is processed
- **WHEN** 目标图片为现有流程支持的视频或序列
- **THEN** 系统依据节点播放设置和现有处理帧数约定取得输入，结果序列保留对应播放时间位置

### Requirement: Results replace the image at the target node

系统 SHALL 在成功后保留目标节点、位置、连线和纹理设置，并在该节点使用结果图片。源图独占时 SHALL 保留 Image 身份、名称与 Fake User；源图有其他实际使用者时 SHALL 仅替换当前节点图片绑定并保持其他使用者和原图不变。结果 SHALL 继承源色彩空间、正确保存透明信息并支持保存重开。

#### Scenario: A sole image is processed
- **WHEN** 目标节点独占源图并完成去背景或放大
- **THEN** 原 Image 内容及尺寸更新为结果，身份和名称保留，临时结果被释放

#### Scenario: Other users share the image
- **WHEN** 另一纹理节点或 Empty 等数据使用者仍引用源图
- **THEN** 当前节点使用独立处理结果，其他使用者继续使用未改变的原图

#### Scenario: Only a fake user is present
- **WHEN** 源图除当前节点外只有 Fake User 或编辑器显示引用
- **THEN** 系统保留源 Image 身份并更新内容

#### Scenario: Background removal succeeds
- **WHEN** 用户对节点执行 Remove Background 成功
- **THEN** 图片带有处理后的透明信息，材质原有连线和渲染设置保留

### Requirement: Asynchronous completion keeps the original target

系统 SHALL 将结果提交到发起任务时的节点，并在提交前验证原节点和图片绑定仍有效。

#### Scenario: Active selection changes
- **WHEN** 处理期间用户切换编辑器、材质或活动节点
- **THEN** 结果仍提交到原节点

#### Scenario: The target is renamed
- **WHEN** 原节点或所属材质在任务期间改名且绑定仍有效
- **THEN** 结果提交到同一原节点

#### Scenario: The original target is invalid
- **WHEN** 原节点被删除、同名重建、变为只读或改绑图片
- **THEN** 系统报告目标失效，保留现有节点和图片状态，并清理本次结果

### Requirement: Edits support failure recovery and undo

系统 SHALL 在失败或取消时保持或恢复原图片内容、节点绑定和播放设置，并清理临时资源。成功操作 SHALL 支持一次撤销还原及重做恢复。

#### Scenario: Commit fails
- **WHEN** 写入图片内容或绑定、配置播放设置期间发生错误
- **THEN** 节点绑定与原图完整恢复，其他使用者保持不变

#### Scenario: The user undoes and redoes an edit
- **WHEN** 用户撤销一次成功操作，然后重做
- **THEN** 撤销恢复原图、尺寸、绑定和播放设置，重做恢复处理结果且无需再次推理
