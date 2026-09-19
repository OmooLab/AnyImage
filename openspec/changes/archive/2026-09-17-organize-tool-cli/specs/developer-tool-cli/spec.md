## Purpose

为 AnyImage 开发者提供按业务对象组织的命令接口，明确节点组构建、检查与预览，以及模型准备与同步的执行边界，将模型下载和导出统一归入准备流程，让每个动作的产物、失败状态和副作用均可验证。

## ADDED Requirements

### Requirement: Grouped command entry points

系统 SHALL 提供 `uv run node-group` 和 `uv run model` 入口，使用小写子命令，并移除旧脚本入口 `build-nodes`、`sync-models`。

#### Scenario: Display help
- **WHEN** 用户未指定子命令或传入 `--help`
- **THEN** 命令显示帮助并成功退出，不启动 Blender、模型准备或上传

#### Scenario: Invalid arguments
- **WHEN** 用户传入未知子命令或参数
- **THEN** 命令显示参数错误并非零退出，业务动作不执行

### Requirement: Build and check node groups

`node-group build` SHALL 依次构建资产、校验保存的资产、运行全量 pytest；`node-group check` SHALL 仅执行后两步。两者 SHALL 支持 `--blender` 选择 Blender，支持 `--skip-tests` 仅跳过 pytest。

#### Scenario: Build assets
- **WHEN** 用户运行 `uv run node-group build`
- **THEN** 更新 O_AnyImage.blend，并在资产校验和全量测试成功后成功退出

#### Scenario: Check existing assets
- **WHEN** 用户运行 `uv run node-group check`
- **THEN** 检查已有资产并运行全量测试，资产文件内容保持原样

#### Scenario: Skip Python tests
- **WHEN** build 或 check 指定 `--skip-tests`
- **THEN** 仍执行资产校验，跳过 pytest

#### Scenario: Stop after failure
- **WHEN** 构建、校验或测试任一步失败
- **THEN** 命令非零退出且不执行后续步骤

### Requirement: Preview node groups

`node-group preview` SHALL 从当前源码在内存中构建并排列几何节点组，生成 HTML，输出绝对路径并默认打开浏览器，保持资产文件内容原样。默认文件 SHALL 保存于系统临时目录并在命令退出后可供查看。命令 SHALL 支持 `--blender`、`--output PATH`、`--no-open` 和 `--fragment`。

#### Scenario: Preview current source
- **WHEN** 用户运行 `uv run node-group preview`
- **THEN** 生成当前源码的可查看 HTML 并尝试打开浏览器

#### Scenario: Save without opening
- **WHEN** 用户指定 `--output PATH --no-open`
- **THEN** HTML 写入指定路径且不启动浏览器

#### Scenario: Export fragment
- **WHEN** 用户指定 `--fragment`
- **THEN** 输出 HTML 片段及其路径，不自动打开浏览器

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
