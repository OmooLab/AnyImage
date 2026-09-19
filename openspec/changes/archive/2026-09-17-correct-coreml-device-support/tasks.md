## 1. 统一 CoreML 设备协议

- [x] 1.1 将 Blender 设备标签、Enum 值、任务参数和 ONNX Provider 映射中的 `mps` 全部替换为 `coreml`，删除旧值的兼容路径。
- [x] 1.2 删除 Apple 芯片品牌解析、`sysctl` 调用和 M4 代际限制，按 macOS arm64/aarch64 平台提供 `coreml` 与 `cpu`。
- [x] 1.3 调整设备枚举测试，覆盖 M1–M4 所在的 macOS arm64、非 Apple Silicon 平台、Manifest 设备清单和旧 `mps` 值拒绝行为。
- [x] 1.4 在全部 Apple Silicon Mac 上默认选择 CPU，并保留 CoreML 手动选项。

## 2. 恢复 MoGe-2 CoreML 兼容性

- [x] 2.1 让共享 Session 工厂默认使用普通 `CoreMLExecutionProvider`，同时支持可选模型级 CoreML options；显式 CoreML 选择保留 CPU fallback，CUDA arena 配置不变。
- [x] 2.2 更新共享 ONNX Runtime 测试，验证默认配置、可选 CoreML options、显式/自动 CPU fallback 以及 `mps` 拒绝行为。
- [x] 2.3 让 MoGe-2 CoreML Session 传入 `RequireStaticInputShapes=1` 且不强制 `MLProgram`，更新测试并保持动态图片与 `num_tokens` 输入不变。

## 3. 文档与验证

- [x] 3.1 更新用户设备说明和 `docs/internals/runtime.md`，统一使用 CoreML，并说明它由 Apple CPU、GPU 与 Neural Engine 调度而非 PyTorch MPS。
- [x] 3.2 运行 `uv run pytest tests/test_blender_addon.py tests/test_model_onnx_runtime.py tests/test_model_moge2_onnx.py tests/test_docs.py`。
- [x] 3.3 在可用的 M2 或 M4 设备选择 CoreML，分别完成 MoGe-2、BEN2 和 Upscale 的单次 smoke test，确认 MoGe-2 不再出现 CoreML 计划构建或预测执行错误。
