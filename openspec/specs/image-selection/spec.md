# image-selection Specification

## Purpose
TBD - created by archiving change unify-selection-terminology. Update Purpose after archive.
## Requirements
### Requirement: Image selection uses one business term
系统 SHALL 在 Image Tool、Cutout Tool 及其对外 Job 协议中使用 Selection 表示用户在图片上圈定并栅格化的范围。

#### Scenario: Selection passes through a tool workflow
- **WHEN** 用户使用图片手势圈定范围并提交工具操作
- **THEN** 工具状态、Job 参数和 Job 结果中表示该范围的字段使用 Selection 术语

### Requirement: Selection refinement option is named Refine Selection
支持 AI 选区细化的工具 SHALL 将对应布尔选项显示为 **Refine Selection**，且开启后只细化当前 Selection 中的前景内容。

#### Scenario: User enables selection refinement
- **WHEN** 用户在 Image Box、Image Lasso 或 Cutout 中开启 **Refine Selection**
- **THEN** 系统使用 AI 将当前 Selection 收紧到其中的前景内容

### Requirement: Cutout normal option is named Normal Map
Cutout Tool SHALL 将控制法线贴图生成的布尔选项显示为 **Normal Map**，并保持现有 Normal Map 生成行为。

#### Scenario: User enables Normal Map
- **WHEN** 用户在 Cutout 中开启 **Normal Map** 并选择可执行该功能的 Shape
- **THEN** 系统按该 Shape 的既定 Normal Space 生成并应用 Normal Map

### Requirement: Cutout mesh detail uses named presets
Cutout Tool SHALL 使用 **Mesh Detail** 档位选择控制网格采样密度，并将 Low、Medium、High、Ultra 分别映射为 32、16、8、4 px 的采样间距。

#### Scenario: User chooses mesh detail
- **WHEN** 用户选择任一 **Mesh Detail** 档位并创建 Cutout Shape
- **THEN** 系统使用该档位对应的采样间距构建网格，且从 Low 到 Ultra 逐档增加采样密度

#### Scenario: User keeps the default mesh detail
- **WHEN** 用户未修改 **Mesh Detail**
- **THEN** 系统使用 Low 对应的 32 px 采样间距

