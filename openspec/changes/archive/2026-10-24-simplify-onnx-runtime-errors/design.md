## Context

所有 ONNX 模型已经通过 `onnx_runtime.py` 创建和运行 Session，但资源错误转换仍由 Upscale 单独实现。ONNX Runtime 的 Python 异常通常直接继承 `Exception` 而不是 `RuntimeError`，现有局部捕获无法形成可靠边界；显式设备请求还可能静默回退到其他 Provider。

## Goals / Non-Goals

**Goals:**

- 以共享的 `create_session()` 和 `run_session()` 作为唯一 ONNX Runtime 异常边界。
- 为模型加载、模型运行、明确资源不足和无法解码的 Provider 错误提供简短且准确的用户提示。
- 让显式设备选择对应实际执行 Provider，让 `auto` 独立承担自动回退职责。
- 删除 Upscale 已被共享层取代的重复逻辑。

**Non-Goals:**

- 不调整模型缓存、Session 释放、arena shrinkage 或推理分辨率。
- 不为每个模型建立单独异常类型或包装函数。
- 不隐藏模型契约验证、输入处理和输出处理自身的错误。

## Decisions

### 1. 只在两次外部调用处建立异常边界

`create_session()` 包装 `onnxruntime.InferenceSession()`，`run_session()` 包装 `session.run()`。共享层不包围模型预处理、输出验证或业务编排，因此不会把项目自身的编程错误误判为 Provider 错误。

采用少量内部辅助函数识别错误并生成消息。共享层仅用一个 `RuntimeError` 子类标记资源失败，使既有 Upscale 生命周期可以释放失效 Session；其他失败使用普通 `RuntimeError`。两者都保留原始异常链，并符合现有 Job 和 Blender Operator 的错误协议。

### 2. 资源错误采用保守判断

`MemoryError` 及包含既有内存不足关键词的 Provider 异常报告 GPU 或系统内存不足。Provider 调用内出现 `UnicodeDecodeError` 时，说明 ONNX Runtime 未能解码底层错误，提示内存不足是常见可能原因，但不将其表述为已确认事实。

其他异常保留原始消息，并补充发生在模型加载还是模型运行阶段。这样既避免裸露异常类型，也不丢失诊断信息。

### 3. 显式设备严格匹配，自动选择继续回退

`auto` 按现有优先级返回所有可用 Provider。显式 `cuda`、`directml`、`coreml` 或 `cpu` 只选择对应 Provider；不可用时直接说明所请求 Provider 不可用。

CoreML 现有的 CPU 后备仍属于 CoreML Session 的执行配置，不改变。CUDA 不再把 DirectML 当作替代项，DirectML 也不再静默退回 CPU。

### 4. Upscale 只保留自身内存边界

Upscale 删除 Provider OOM 关键词、Unicode 解码捕获及专用 Provider 异常。完整输出数组在 Python/NumPy 层发生的 `MemoryError` 仍由 Upscale 转换，因为该错误不经过 ONNX Runtime 共享入口。

MoGe、BEN2 与 BiRefNet 不增加代码；它们通过现有共享调用自动获得一致行为。

## Risks / Trade-offs

- [部分驱动的 OOM 文本不包含已知关键词] → 保留原始 Provider 消息和运行阶段上下文，后续可依据真实报告补充最小关键词集合。
- [Unicode 解码失败不一定由内存不足引起] → 使用“可能”的提示，不做确定归因，并保留原始异常作为异常链。
- [显式设备不可用时不再继续执行] → 用明确失败换取设备语义可信；需要自动回退的调用使用 `auto`。
- [统一转换会改变测试期待的异常类型] → 测试共享用户可见合同，不依赖 ONNX Runtime 的私有异常层级。

## Migration Plan

1. 在共享 ONNX Runtime 模块加入错误转换，并补齐创建与运行测试。
2. 收紧显式 Provider 选择测试，同时保留 `auto` 和 CoreML CPU 后备行为。
3. 删除 Upscale 重复转换，保留完整输出的系统内存错误并更新测试。
4. 运行相关 AI 测试；回退时整体恢复共享入口与 Upscale 局部逻辑，无数据迁移。

## Open Questions

无。
