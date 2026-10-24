## Why

三个模型类别槽位能避免 Remove Background 与 Cutout 连用时反复冷启动，但资源不足后仍可能留下其他常驻 Session，继续占用内存并影响 Blender。系统需要只在明确的 ONNX 资源失败时自动回收缓存，同时保留用户随时主动卸载模型的控制权。

## What Changes

- 保留 background、geometry 和 upscale 三个常驻槽位，不增加空闲超时或自动定时清理。
- Session 创建因资源不足失败时，清空全部模型 Session，并仅重试当前模型加载一次。
- 模型推理因资源不足失败时，清空全部模型 Session并返回原错误，不自动重试推理。
- 普通模型错误、输入错误和任务取消不触发模型卸载。
- 在 AnyImage 图片、对象和纹理节点右键菜单中提供现有 `Unload Models` 操作；Server 忙碌或未运行时不可执行。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `model-inference-memory`: 增加 ONNX 资源失败时的缓存清理、有限加载重试和推理失败行为。
- `server-cache-display`: 将模型卸载控制扩展到 AnyImage 右键菜单，并规定可用状态。

## Impact

- 依赖已完成变更 `simplify-onnx-runtime-errors` 提供的共享 `OnnxResourceError`。
- 影响 `server/model_manager.py`、AI Job 的统一执行边界、AnyImage 右键菜单和 `ClearModels` 可用性。
- 不改变模型文件、Job 参数、推理输出、三个缓存槽位或手动清理的既有含义。
