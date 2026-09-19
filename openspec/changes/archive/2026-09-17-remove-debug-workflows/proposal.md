## Why

模型调试入口已完成阶段性用途，继续保留会增加 UI、参数、Job 和测试的维护成本。结合删除工作，全面整理测试、节点资产源码和内部文档，让名称、职责、验证与实际功能保持一致。

## What Changes

- **BREAKING**：移除 Debug 主面板、DA3 / MoGe-2 / BEN2 / Upscale 子面板及四个 `anyimage.debug_*` Operator。
- **BREAKING**：移除 `debug-da3`、`debug-moge2`、`debug-ben2`、`debug-upscale` Job 和原始预测导出实现。
- 删除 Debug 专用 Scene 属性、UI 辅助函数、参数组装、序列化与帧复制代码，清理注册、导入和导出。
- 删除当前仅由 Debug 调用的 DA3 模型适配器、ONNX 推理、目录声明及缓存分支；Upscale 统一保留源 Alpha。
- 根据正式功能的实际引用保留共用模型、输入处理、设备设置、视频帧数和推理能力。
- 调整注册、Job、模型及打包测试，覆盖删除后的边界和正式功能回归。
- 全面审查 `tests/` 的文件、测试类、用例和辅助代码，仅保留能发现实际行为回归或约束关键协议的测试，按验证功能整理名称和归属。
- 全面梳理 `tools/node_assets/` 的构建、几何、布局及验证职责，重命名或拆并职责不符的模块，同步所有导入与脚本引用。
- 全面重整 `docs/internals/`，逐页对照最终源码与功能逻辑修订内容、文件名和索引，清理 Debug 说明并同步 `mkdocs.yml` 导航。

## Capabilities

### New Capabilities

- `production-only-ai-workflows`：约束扩展仅暴露正式 AI 工作流，规定 Debug 入口及专用实现的移除和正式功能的可用性。
- `maintainable-project-structure`：规定测试价值与命名、节点资产模块职责和内部文档与实现的一致性。

### Modified Capabilities

无。当前 `openspec/specs/` 尚无已归档规范。

## Impact

- Blender：`panel.py`、`properties.py`、扩展与 Operator 注册、`operators/debug.py`、`common/ai.py`。
- Server：`app.py`、`jobs/debug_predictions.py`、`outputs/`、`media/` 及仅被 Debug 引用的模型适配辅助逻辑。
- 测试：整个 `tests/`，包含测试归属、名称、公共 fixture 和重复覆盖的整理。
- 节点资产：整个 `tools/node_assets/`，以及 `tools/build_node.py`、相关测试和调用引用。
- 文档：整个 `docs/internals/` 及 `mkdocs.yml` 导航；按用户明确要求同步实现说明。
- 本次整理运行测试，不构建文档、扩展包或节点资产；节点资产整理保持现有节点图与资产接口行为。
