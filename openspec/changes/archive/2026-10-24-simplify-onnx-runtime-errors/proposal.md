## Why

ONNX Runtime 的加载与推理异常目前只在 Upscale 局部转换，MoGe 与 Remove Background 会直接暴露底层异常，内存不足时甚至可能显示无关的 UTF-8 解码错误。设备选择还会在显式 Provider 不可用时静默回退，使界面提示、性能和实际执行设备不一致。

## What Changes

- 由共享 ONNX Runtime 入口统一转换 Session 创建和推理异常，向所有模型提供一致、可读的错误。
- 识别明确的内存不足错误；对于 Provider 报错时出现的 Unicode 解码失败，提示可能的 GPU 或系统内存不足而不声称已经确定原因。
- 删除 Upscale 重复的 Provider 错误判断，仅保留其自身输出数组分配失败的业务提示。
- `auto` 继续自动选择可用 Provider；用户显式选择的 CUDA、DirectML、CoreML 或 CPU 不可用时直接报错，不再静默换用其他设备。
- 不调整模型缓存数量、Session 生命周期、推理内存释放时机或模型输出。

## Capabilities

### New Capabilities

- `onnx-runtime-boundary`: 规定共享 ONNX Runtime 的 Provider 选择、Session 创建和推理错误呈现。

### Modified Capabilities

- `model-inference-memory`: 将 Upscale 专属的资源错误合同改为所有 ONNX 模型共享的资源错误合同，不改变内存释放行为。

## Impact

- 影响 `src/anyimage/server/models/onnx_runtime.py` 及 Upscale 的局部异常处理。
- MoGe、BEN2、BiRefNet 和 Upscale 通过既有共享入口自动获得一致行为，无需新增模型层胶水代码。
- 更新相关 AI 单元测试；不新增依赖，不修改公开 Job 参数和产物。
