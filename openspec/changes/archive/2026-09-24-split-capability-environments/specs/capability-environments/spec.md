## ADDED Requirements

### Requirement: Capability-oriented dependency groups

项目 SHALL 使用默认 `dev` 及 `blender`、`ai`、`models` 和 `docs` 依赖组分别表达通用开发、Blender 集成、AI 推理、模型资产生产和文档构建能力。非默认能力组 SHALL 仅包含其职责所需的增量依赖。

#### Scenario: Install Blender development environment
- **WHEN** 开发者或 CI 仅选择 `blender` 能力组
- **THEN** uv 自动加载默认 `dev` 及 Blender 验证所需依赖，不安装 AI 推理、模型资产生产或文档构建专用依赖

#### Scenario: Install AI development environment
- **WHEN** 开发者选择 `ai` 能力组
- **THEN** 环境包含本地 AI 推理及其测试所需依赖

#### Scenario: Install model production environment
- **WHEN** 开发者选择 `models` 能力组
- **THEN** 环境包含模型下载、转换和导出所需依赖，且该组不成为常规 CI 的前置条件

### Requirement: Test categories follow execution requirements

测试 SHALL 根据实际执行环境分目录。只有要求 AI 专用运行时或模型实现的测试 SHALL 位于 `tests/ai`；使用 mock 验证 AI 界面、任务协议、参数传递和失败处理的测试 SHALL 留在常规业务测试目录。

#### Scenario: Run CI test set
- **WHEN** 在只安装 `blender` 及其基础能力的环境执行常规测试目录
- **THEN** 测试收集和执行成功，且不要求 AI 或模型资产生产专用依赖

#### Scenario: Run local AI test set
- **WHEN** 开发者安装 `ai` 能力并执行 `tests/ai`
- **THEN** 只执行明确归类的 AI 模型运行与实现测试

#### Scenario: Protect mocked AI integration
- **WHEN** AI 相关测试不加载真实模型运行时且只验证产品集成契约
- **THEN** 该测试包含在常规 CI 集合中

### Requirement: Continuous integration excludes local-only capabilities

普通测试工作流和发布工作流 SHALL 使用默认 `dev`、显式选择 Blender 能力并直接运行常规测试目录，不得同步 `ai`、`models` 或 `docs` 能力组。项目命令 SHALL 不要求关闭默认依赖组。

#### Scenario: Pull request validation
- **WHEN** 测试工作流在 pull request 或主分支运行
- **THEN** 工作流完成非 AI 测试，且依赖同步不包含 AI、模型生产和文档专用包

#### Scenario: Release validation
- **WHEN** 发布工作流构建扩展包
- **THEN** 发布前运行与普通 CI 相同的非 AI 测试门禁，不运行本地 AI 测试
