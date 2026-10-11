# developer-tool-cli Specification

## Purpose
TBD - created by archiving change organize-tool-cli. Update Purpose after archive.
## Requirements
### Requirement: Grouped command entry points

系统 SHALL 通过 `uv run --group blender omoonodes` 管理节点资产，通过 `uv run model` 管理模型，使用小写子命令。

#### Scenario: Display help
- **WHEN** 用户传入 `--help`
- **THEN** 命令显示帮助并成功退出，不执行构建、模型准备或上传

#### Scenario: Invalid arguments
- **WHEN** 用户传入未知子命令或参数
- **THEN** 命令显示参数错误并非零退出，业务动作不执行

### Requirement: Build and validate node assets

`omoonodes build` SHALL 默认读取 `nodes/`，使用默认 `b45` 目标及工具包准备的隔离 Blender 环境，将校验通过的资产库输出到 `dist/b45/O_AnyImage/`。项目 SHALL 将生成的 `O_AnyImage.blend` 复制到 `src/anyimage/assets/`，再独立运行节点测试。

#### Scenario: Build assets
- **WHEN** 用户运行 `uv run --group blender omoonodes build`
- **THEN** 构建并校验 nodebpy 源码定义的资产库，成功后更新输出目录

#### Scenario: Validate saved assets
- **WHEN** 用户复制生成资产并运行 `uv run --group blender pytest tests/nodes`
- **THEN** 测试验证节点求值、接口、布局、属性协议和保存资产

#### Scenario: Stop after failure
- **WHEN** 构建或校验失败
- **THEN** 命令非零退出，正式输出保持完整

### Requirement: Edit and import node assets

系统 SHALL 通过 `omoonodes dev` 生成 Blender 开发库，通过 `dev --sync` 将编辑结果同步回 nodebpy 源码；首次导入 SHALL 使用 `dump`，导入前将节点组标记为 Asset 并保存。

#### Scenario: Edit current source
- **WHEN** 用户运行 `uv run --group blender omoonodes dev nodes/O_AnyImage`
- **THEN** 开发库生成于 `workspaces/b45/O_AnyImage/`，可在 Blender 中编辑

#### Scenario: Sync edited assets
- **WHEN** 用户保存开发库并运行 `uv run --group blender omoonodes dev nodes/O_AnyImage --sync workspaces`
- **THEN** 编辑结果经校验后同步回资产库源码

#### Scenario: Import an asset library
- **WHEN** 用户将包含 Asset 节点组的文件通过 `omoonodes dump` 导出到尚不存在的源码目录
- **THEN** 工具生成 nodebpy 源码和 `collection.json`，并校验往返构建

### Requirement: Prepare and sync models

模型命令 SHALL 提供 `prepare` 和 `sync` 两个子命令。`model prepare` SHALL 准备并校验目录中全部模型，复用有效缓存，按模型来源下载现成 ONNX 或准备源权重并导出（包含 PiSA-SR）；`model sync` SHALL 在全部准备成功后上传 R2。`prepare` SHALL 不上传且不要求上传工具可用。

#### Scenario: Prepare locally
- **WHEN** 用户运行 `uv run model prepare`
- **THEN** 全部模型在本地通过既有大小和 SHA-256 校验，不执行上传

#### Scenario: Sync prepared models
- **WHEN** 用户运行 `uv run model sync` 且全部准备成功
- **THEN** 上传全部模型到既定 R2 位置

#### Scenario: Preparation fails
- **WHEN** 任一模型准备或校验失败
- **THEN** 命令非零退出，sync 不开始上传

#### Scenario: Download and export models
- **WHEN** 用户运行 `uv run model prepare` 且本地缺少有效模型
- **THEN** 根据模型来源下载现成文件或准备源权重并导出，产物保存到既有本地目标并通过校验

#### Scenario: Reuse valid cache
- **WHEN** 本地模型已通过大小和 SHA-256 校验
- **THEN** prepare 复用该产物，跳过对应下载和导出

#### Scenario: Export fails
- **WHEN** 源权重准备、转换或产物校验失败
- **THEN** 命令非零退出，失败产物不替换正式目标

### Requirement: Capability-specific test commands

项目 SHALL 提供明确的 uv 命令分别运行常规 CI 测试、本地 AI 测试和本地全量测试。命令 SHALL 使用默认 `dev` 并显式增加所需能力组，不要求传入 `--no-default-groups`。

#### Scenario: Run regular validation
- **WHEN** 开发者运行常规验证命令
- **THEN** 命令安装核心与 Blender 能力并执行所有非 AI 测试

#### Scenario: Run AI validation locally
- **WHEN** 开发者运行 AI 验证命令
- **THEN** 命令安装 AI 能力并仅执行 AI 测试

#### Scenario: Run full validation locally
- **WHEN** 开发者运行全量验证命令
- **THEN** 命令安装 Blender 与 AI 能力并执行全部测试

