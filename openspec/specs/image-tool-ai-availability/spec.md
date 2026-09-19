# image-tool-ai-availability Specification

## Purpose
TBD - created by archiving change gate-cutout-ai-options. Update Purpose after archive.
## Requirements
### Requirement: AI setup entry precedes dependent tool settings
当 AI 环境或所需模型未就绪时，系统 SHALL 在 Cutout、Image Box 和 Image Lasso 的工具设置开头显示 AI 设置按钮，并使用当前 AI 状态对应的设置文案。

#### Scenario: Cutout AI setup entry is first
- **WHEN** AI 未就绪且用户激活 Cutout 工具
- **THEN** 工具设置 SHALL 先显示 AI 设置按钮，再显示 `Fit to Foreground`、`Mesh Sampling Spacing` 和 `Generate Normal Map`

#### Scenario: Image region tool AI setup entry is first
- **WHEN** AI 未就绪且用户激活 Image Box 或 Image Lasso
- **THEN** 工具设置 SHALL 先显示 AI 设置按钮，再显示 `Fit to Foreground`

#### Scenario: AI setup entry is omitted when ready
- **WHEN** AI 环境和所需模型均已就绪
- **THEN** Cutout、Image Box 和 Image Lasso 的工具设置 SHALL 不显示 AI 设置按钮

### Requirement: AI-dependent settings follow AI availability
系统 SHALL 仅在 AI 环境和所需模型均已就绪时允许启用图像区域工具的 AI 依赖设置。

#### Scenario: Dependent settings are disabled without AI
- **WHEN** AI 未就绪
- **THEN** Cutout 的 `Fit to Foreground` 和 `Generate Normal Map` SHALL 不可编辑
- **THEN** Image Box 和 Image Lasso 的 `Fit to Foreground` SHALL 不可编辑
- **THEN** Cutout 的 `Mesh Sampling Spacing` SHALL 保持可编辑

#### Scenario: Dependent settings are enabled with AI
- **WHEN** AI 环境和所需模型均已就绪
- **THEN** Cutout 的 `Fit to Foreground` 和 `Generate Normal Map` SHALL 可编辑
- **THEN** Image Box 和 Image Lasso 的 `Fit to Foreground` SHALL 可编辑

### Requirement: Cutout shape choices follow AI availability
系统 SHALL 根据 AI 可用性限制 Cutout shape pie 中的可选 shape，同时保留四种 shape 的底层实现。

#### Scenario: Two local shapes without AI
- **WHEN** AI 未就绪且用户完成 Cutout 区域选择
- **THEN** shape pie SHALL 只显示 `Surface` 和 `Balloon`

#### Scenario: Four shapes with AI
- **WHEN** AI 环境和所需模型均已就绪且用户完成 Cutout 区域选择
- **THEN** shape pie SHALL 显示 `Surface`、`Balloon`、`Depth Balloon` 和 `Depth Surface`

#### Scenario: Runtime RNA menu shape assignment
- **WHEN** a displayed Cutout shape is selected on a Blender version that exposes modifier inputs through runtime RNA
- **THEN** the system SHALL assign the matching string enum identifier and create the shape successfully

### Requirement: Stale AI settings do not trigger generation
系统 MUST 在区域交互读取设置时忽略 AI 未就绪状态下遗留为真的 AI 依赖选项。

#### Scenario: Local Cutout remains local with stale settings
- **WHEN** AI 未就绪、`Fit to Foreground` 或 `Generate Normal Map` 的保存值为真，且用户选择 `Surface` 或 `Balloon`
- **THEN** Cutout operator SHALL 接收关闭的 AI 依赖选项
- **THEN** 操作 SHALL 不因这些遗留值启动 AI job 或打开 AI 设置流程

