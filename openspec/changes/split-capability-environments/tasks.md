## 1. 拆分能力环境

- [x] 1.1 将 `pyproject.toml` 拆为默认 `dev` 及 `blender`、`ai`、`models` 和 `docs` 增量能力组，并保持现有版本约束
- [x] 1.2 检查模型 CLI、打包和节点工具的真实 import 链，修正依赖归属并确保各能力组可独立同步
- [x] 1.3 刷新 `uv.lock`，确认常规 Blender 环境不包含 AI、模型生产和文档专用包

## 2. 分类测试

- [x] 2.1 将模型实现、推理和后处理测试移动到独立的 `tests/ai` 目录
- [x] 2.2 保留使用 mock 的 AI 界面、Operator、任务协议、模型目录、下载和失败处理测试在非 AI 集合
- [x] 2.3 消除非 AI 测试收集阶段对 AI 与模型生产专用依赖的顶层导入
- [x] 2.4 更新测试命令相关测试，使常规、AI 和全量验证的能力组与 pytest 选择条件受到覆盖

## 3. 精简 CI

- [x] 3.1 修改 `.github/workflows/test.yml`，只选择 `blender` 能力并直接运行常规测试目录
- [x] 3.2 修改 `.github/workflows/release.yml`，使用与普通 CI 一致的测试环境和常规测试目录

## 4. 验证

- [x] 4.1 在不安装 `ai`、`models` 和 `docs` 能力的环境运行全部常规测试目录
- [x] 4.2 在本地 AI 环境运行 AI 测试，并在 Blender 与 AI 能力同时启用时运行全量测试
- [x] 4.3 检查最终差异和 uv 依赖树，确认 CI 路径不会下载 `torch`、`onnx`、`onnxruntime`、`huggingface-hub` 或文档工具链
