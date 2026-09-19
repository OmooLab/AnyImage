## ADDED Requirements

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
