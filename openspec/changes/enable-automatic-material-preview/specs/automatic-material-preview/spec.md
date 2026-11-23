## ADDED Requirements

### Requirement: 两个版本共用自动材质预览偏好

完整版和 Lite 的扩展偏好设置 SHALL 提供默认开启的「自动材质预览」，控制该版本已有的 Cutout 和环境转换操作。

#### Scenario: 首次使用或沿用已有偏好

- **WHEN** 用户尚未设置过「自动材质预览」
- **THEN** 该选项默认勾选，包含 Lite 的本地 Cutout 和 Convert to World

#### Scenario: 关闭自动材质预览

- **WHEN** 该选项已关闭，任一适用操作生成结果
- **THEN** 操作正常应用结果，所有视图保留原着色模式和 Scene World 设置

### Requirement: 只调整发起操作的视图

启用该偏好时，插件 SHALL 仅检查发起操作的 3D 视图在应用预览时的着色模式。Solid 和 Wireframe 切换为 Material Preview，Material Preview 和 Rendered 保留当前模式。

#### Scenario: 多个视图间切换焦点

- **WHEN** 用户从视图 A 提交 AI Cutout 或 Panorama，等待期间在视图 B 工作，并在结果返回前将 A 调为 Rendered
- **THEN** 插件按 A 此时的 Rendered 模式应用对应操作的规则，B 的所有视图设置保持原值

#### Scenario: 操作上下文没有 3D 视图

- **WHEN** 操作进入结果应用阶段，但传入上下文没有活动的 3D 视图
- **THEN** 插件跳过视图调整，沿用操作原有的结果处理流程

### Requirement: Cutout 在准备创建物体时显示材质

本地和 AI Cutout SHALL 在输入就绪、即将创建物体时应用模式规则，保留包括 Scene World 在内的其他视图设置。

#### Scenario: AI 结果就绪

- **WHEN** 用户在 Solid 视图发起 Cutout 并等待 AI
- **THEN** 选区交互和等待阶段均保留当前模式，结果就绪且准备添加物体时才切换到 Material Preview

#### Scenario: Lite 本地创建

- **WHEN** Lite 用户在 Wireframe 视图完成选区并选择本地 Cutout 形状
- **THEN** 准备创建物体时切换到 Material Preview，Scene World 保留原值

#### Scenario: Cutout 已能看到材质

- **WHEN** 准备创建 Cutout 时视图已是 Material Preview 或 Rendered
- **THEN** 该视图的着色与光照设置均保持原值

### Requirement: World 和 Panorama 显示场景环境

Convert to World 和 Convert to Panorama 成功应用结果后 SHALL 执行模式规则并勾选最终模式的 Lighting → Scene World。另一模式的 Scene World 和其他视图参数均保留原值。

#### Scenario: 在材质预览中显示新环境

- **WHEN** 任一环境转换成功，发起视图原为 Wireframe、Solid 或 Material Preview
- **THEN** 该视图处于 Material Preview，且该模式的 Scene World 已勾选

#### Scenario: 已在渲染模式下转换

- **WHEN** 任一环境转换成功，发起视图为 Rendered 且其 Scene World 未勾选
- **THEN** 该视图保持 Rendered，并勾选 Rendered 下的 Scene World

#### Scenario: 转换未产生结果

- **WHEN** 环境转换被取消，或 AI 任务失败
- **THEN** 所有视图保留操作前的设置
