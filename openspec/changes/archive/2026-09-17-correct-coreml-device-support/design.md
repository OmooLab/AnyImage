## Context

AnyImage 的 ONNX 推理把设备值 `mps` 映射到 `CoreMLExecutionProvider`，但该名称通常指 PyTorch Metal backend，与实际实现不一致。Blender 端还通过 CPU brand string 将 Apple 加速限制为 M4 及以上，而 macOS 扩展本身只发布 `macos-arm64`，支持范围已经限定为 Apple Silicon。

共享 Session 工厂目前为所有 CoreML 模型强制传入 `ModelFormat=MLProgram`。MoGe-2 的 ONNX 图具有动态空间尺寸、动态 `num_tokens`、控制流和大量 shape 运算，CoreML 在 MacBook M4 上会在 Session 创建阶段因执行计划构建失败；加入该配置前，同一 Provider 使用默认模型格式可以运行。

## Goals / Non-Goals

**Goals:**

- 让设备名称准确表达 CoreML Execution Provider。
- 在全部受支持的 macOS arm64 设备上提供 CoreML。
- 恢复 MoGe-2 在 MacBook M4 CoreML 模式下的 Session 创建与推理。
- 保持共享 ONNX Session 工厂简单，并保留 CPU fallback。

**Non-Goals:**

- 引入 PyTorch 或实现 PyTorch MPS backend。
- 保证所有 CoreML 算子只在 GPU 上执行。
- 支持 macOS x64、iOS 或新的模型格式。
- 保留 `mps` 任务值、配置值或转发映射。

## Decisions

### 1. 使用 `coreml` 作为唯一 Apple 加速设备标识

Blender Enum、Job 参数、运行时设备清单和 Provider 选择表统一使用小写 `coreml`，界面显示 `CoreML`。旧 `mps` 标识直接删除，因为它描述的是不同的推理 API；增加别名会继续扩大协议边界并违反项目不保留兼容层的约束。

### 2. 按平台能力判断 CoreML，不按芯片代际判断

macOS 且机器架构为 `arm64` 或 `aarch64` 时提供 `coreml` 和 `cpu`，其他 Unix 平台只提供 `cpu`，Windows 维持 DirectML 与 CPU。删除 CPU brand string 正则、`sysctl` 子进程和 M4 代际测试。这样支持范围与 `macos-arm64` 扩展包以及 ONNX Runtime macOS arm64 wheel 一致。

保留 M4 门槛的替代方案被放弃，因为它不是 Provider 能力判断，只会让 M1–M3 在具备 CoreML 时被迫使用 CPU。

### 3. 默认 CoreML 配置与 MoGe-2 静态分区配置分离

共享 Session 工厂默认向 ONNX Runtime 传递普通的 `CoreMLExecutionProvider` 名称，不再为所有模型强制 `MLProgram`。它同时接受可选的模型级 CoreML options；只有调用方明确提供时才把 CoreML Provider 配置为 tuple。CUDA 的独立 arena 配置保持不变。

MoGe-2 传入 `RequireStaticInputShapes=1`，使 CoreML EP 只接管输入 shape 已静态确定的分区，动态空间尺寸、动态 `num_tokens` 和相关控制流留给 CPU fallback。BEN2、DA3 与 Upscale 不携带该选项，继续使用普通 CoreML 配置。

该决定取代“所有模型都使用普通 CoreML 配置”的原方案：M2 真机证明 NeuralNetwork 格式虽然能创建 MoGe-2 Session，但动态 CoreML 分区仍会在执行时失败。也不选择 `CPUAndGPU`，因为故障来自动态图兼容性，而不是 Neural Engine 选择；不选择整体强制 CPU，因为静态限制仍允许安全分区使用 CoreML。

### 4. macOS 界面默认 CPU，CoreML Session 保持 CPU fallback

macOS arm64 的设备枚举把 CPU 放在 CoreML 之前，使新安装和未保存设备选择时默认使用 CPU。CoreML 的性能取决于模型和设备，用户需要时可手动选择，不根据芯片代际自动启用。

显式选择 `coreml` 时仍以 `CoreMLExecutionProvider` 为首选并显式附带 `CPUExecutionProvider`；共享 Session 工厂的自动 Provider 顺序也保持不变。这样 MoGe-2 被静态限制排除的动态节点具有确定的 CPU fallback；明确选择 CPU 时则只请求 CPU Provider。

## Risks / Trade-offs

- [CoreML 默认配置在未来 ONNX Runtime 版本中可能变化] → 固定 ONNX Runtime 版本，并以 Session 参数测试保证 AnyImage 不再主动强制 `MLProgram`。
- [MoGe-2 静态分区限制可能减少 CoreML 加速比例] → 接受 CPU fallback 以换取正确性，并用真机 smoke test 验证；不把 CoreML 设备描述为纯 GPU。
- [M1–M3 未覆盖真实设备集成测试] → 单元测试覆盖平台枚举，并在可用 Apple Silicon 设备上执行 MoGe-2 smoke test；真实失败仍可选择 CPU。
- [旧 Blender 配置保存了 `MPS`] → 这是明确的 breaking rename；不解析旧值，用户在新版中选择 `CoreML` 或 `CPU`。
- [CoreML 不保证纯 GPU] → 界面和文档只承诺 CoreML，不再使用 Metal/MPS 或纯 GPU 表述。

## Migration Plan

1. 同步替换设备协议与界面枚举中的 `mps` 为 `coreml`，删除芯片代际检测。
2. 移除共享的强制 CoreML options，让普通模型使用默认配置，并让 MoGe-2 单独传入 `RequireStaticInputShapes=1`。
3. 更新测试和内部文档，再运行相关单元测试。
4. 在可用的 M2 或 M4 设备选择 CoreML，分别执行 MoGe-2、BEN2 和 Upscale smoke test；MoGe-2 必须完成 Session 创建和一次推理。

若真实设备验证失败，回滚本变更并使用 CPU；不重新引入 `mps` 兼容层。

## Open Questions

无。
