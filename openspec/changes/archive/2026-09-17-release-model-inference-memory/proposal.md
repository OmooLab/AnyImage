## Why

ONNX Runtime 会把模型权重与推理期间扩张的 GPU memory arena 一起保留在长期存活的 Session 中；一次高显存推理结束后，临时分配继续挤占 Blender 的 GPU 资源。模型 Session 需要继续缓存以避免重复加载，但 BEN2、DA3、MoGe-2 与 Upscale 的单次推理内存应在业务处理完成后统一释放。

## What Changes

- 为所有 ONNX 模型建立统一的推理运行入口，区分长期缓存的 Session 与单次处理使用的临时 memory arena。
- 让 CUDA Session 使用可收缩的 arena 配置，并在一次图片、帧批次或分块处理的最后一次模型运行后请求回收临时 GPU 分配。
- BEN2、DA3、MoGe-2 与全部 Upscale 模型均使用相同的释放语义，同时继续复用 `ModelManager` 中的原 Session。
- 对不支持 arena shrinkage 的 Execution Provider 保持原推理行为，不提交无效的 Provider 或 Run 配置。
- 增加模型级与 Server 生命周期测试，验证临时内存释放、批次结束边界和 Session 复用。

## Capabilities

### New Capabilities

- `model-inference-memory`: 规定所有 ONNX 模型在复用 Session 的同时，于一次业务推理完成后释放 Provider 支持的临时推理内存。

### Modified Capabilities

无。

## Impact

- 影响 `server/models/onnx_runtime.py`、BEN2、DA3、MoGe-2、Upscale 的 ONNX 适配器及对应测试。
- 影响多帧 BEN2 与分块 Upscale 的运行边界，需要只在最后一次 `session.run()` 请求 arena shrinkage，避免每帧或每块重复释放与重新分配。
- `ModelManager` 的模型族缓存、Job 协议、模型文件、输出文件与外部依赖保持不变。
