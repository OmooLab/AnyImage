## Why

macOS 设备当前以 `mps` 表示实际的 ONNX Runtime CoreML Execution Provider，并人为限制为 M4 及以上；同时强制使用 `MLProgram` 会使具有动态输入和控制流的 MoGe-2 在 MacBook M4 上创建模型时触发 `Error in building plan`。需要让设备名称、支持范围和实际推理后端一致，并恢复 MoGe-2 可用性。

## What Changes

- **BREAKING**：将公开任务参数、运行时设备清单和界面枚举中的设备标识由 `mps` 改为 `coreml`，不保留旧标识兼容层。
- macOS arm64 构建对所有 Apple Silicon 设备提供 CoreML 与 CPU 选项，移除 Apple 芯片代际解析和 M4 最低代际限制。
- Apple Silicon Mac 默认使用 CPU，CoreML 保留为用户手动选择的可选设备。
- 通用 CoreML Session 使用 ONNX Runtime 的兼容默认模型格式，不再强制把所有模型转换为 `MLProgram`。
- MoGe-2 为 CoreML 单独启用静态输入分区限制，只将静态 shape 分区交给 CoreML，并把其余节点交给 CPU Execution Provider。
- 显式保留 CoreML 之后的 CPU fallback，并验证 MoGe-2、BEN2 与 Upscale 的设备选择不回归。
- 同步更新设备相关测试和内部文档，使 `coreml` 明确表示 CoreML 调度的 Apple CPU、GPU 与 Neural Engine，而不是 PyTorch MPS backend。

## Capabilities

### New Capabilities

- `coreml-inference`: 规定 macOS arm64 的 CoreML 设备标识、支持范围、Provider 选择和 MoGe-2 兼容行为。

### Modified Capabilities

无。

## Impact

- 影响 Blender 设备枚举、Job 参数、运行时 Manifest 和 ONNX Runtime Session 创建。
- 影响 `properties.py`、`server/models/onnx_runtime.py`、`server/models/onnx_moge2.py` 及对应测试与内部文档。
- `mps` 设备值会被删除；尚未完成或外部构造的旧任务参数必须改用 `coreml`。
- 不新增依赖，不改变模型文件、模型输出协议或 Blender Operator 标识符。
