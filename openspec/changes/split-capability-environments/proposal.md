## Why

当前开发依赖全部集中在 `dev` 组，常规测试和 CI 会下载模型导出、ONNX 推理及文档构建等无关的大型依赖。需要按业务能力拆分环境，并让 AI 模型测试只在本地显式运行，以降低 CI 的下载量和执行成本。

## What Changes

- 将开发依赖按默认 `dev` 及 `blender`、`ai`、`models`、`docs` 能力分组，不使用仅体现测试用途的 `test-*` 命名。
- 将 AI 模型执行测试集中到独立目录，常规测试保留在现有业务目录。
- CI 和发布流程只安装并运行默认开发与 Blender 集成所需环境，不安装 AI 推理和模型导出依赖。
- 提供明确的本地 AI 测试与全量测试命令。
- 保留不依赖真实模型运行时的 AI 界面、参数、任务协议和错误处理测试在 CI 中。

## Capabilities

### New Capabilities

- `capability-environments`: 定义开发依赖的能力分组、测试分类，以及 CI 与本地测试环境的选择规则。

### Modified Capabilities

- `developer-tool-cli`: 调整项目测试命令，使核心、Blender、AI 和全量验证可以分别执行。

## Impact

- 修改 `pyproject.toml` 的 dependency groups 和 pytest 配置，并刷新 `uv.lock`。
- 调整测试标记及少量测试归属，不改变产品运行时代码和扩展依赖协议。
- 修改 `.github/workflows/test.yml` 与 `.github/workflows/release.yml` 的依赖安装和测试命令。
- 常规 CI 不再下载 `torch`、`onnx`、`onnxruntime`、`huggingface-hub` 和文档工具链；本地仍可运行 AI 与全量测试。
