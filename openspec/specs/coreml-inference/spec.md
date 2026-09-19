# coreml-inference Specification

## Purpose
TBD - created by archiving change correct-coreml-device-support. Update Purpose after archive.
## Requirements
### Requirement: CoreML 使用唯一设备标识
系统 SHALL 在界面、任务参数、运行时设备清单和 ONNX Provider 选择中使用 `coreml` 表示 Apple CoreML Execution Provider，并 SHALL NOT 接受或生成 `mps` 设备标识。

#### Scenario: macOS 用户查看推理设备
- **WHEN** 用户在受支持的 macOS arm64 设备上查看推理设备枚举
- **THEN** 系统显示 `CoreML` 和 `CPU`，且不显示 `MPS`

#### Scenario: CoreML 任务参数
- **WHEN** 用户选择 CoreML 并创建 AI 任务
- **THEN** 系统提交的设备参数为 `coreml`

#### Scenario: 旧设备标识不再受支持
- **WHEN** Provider 选择入口接收到 `mps`
- **THEN** 系统拒绝该值，而不将其转换或转发为 CoreML

### Requirement: Apple Silicon 支持范围按平台确定
系统 SHALL 在 macOS 的 `arm64` 或 `aarch64` 架构上提供 CoreML，不得根据 Apple 芯片代际限制该设备。

#### Scenario: M1 至 M3 设备
- **WHEN** 系统运行于 M1、M2 或 M3 的 macOS arm64 环境
- **THEN** 可用设备包含 `coreml` 和 `cpu`

#### Scenario: M4 或更新设备
- **WHEN** 系统运行于 M4 或更新的 macOS arm64 环境
- **THEN** 可用设备包含 `coreml` 和 `cpu`

#### Scenario: Apple Silicon 默认设备
- **WHEN** macOS arm64 同时提供 CPU 与 CoreML
- **THEN** 设备枚举默认选择 CPU，且用户仍可手动选择 CoreML

#### Scenario: 非 Apple Silicon 平台
- **WHEN** 系统不运行于 macOS arm64 或 aarch64 环境
- **THEN** 系统不因 CoreML 规则新增 `coreml` 设备

### Requirement: CoreML Session 使用模型兼容配置
系统 SHALL 以 `CoreMLExecutionProvider` 创建 CoreML Session，并 SHALL NOT 强制设置 `ModelFormat=MLProgram`。普通模型 SHALL 使用默认 CoreML 配置；MoGe-2 SHALL 只允许 CoreML 接管静态输入 shape 分区；CoreML 不支持或未接管的执行 SHALL 由 CPU fallback 处理。

#### Scenario: 显式选择 CoreML
- **WHEN** 任务请求设备 `coreml` 且 ONNX Runtime 提供 CoreML Execution Provider
- **THEN** Session 以 CoreML 为首选 Provider、以 CPU 为后备 Provider，且创建参数不包含强制的 CoreML `MLProgram` 配置

#### Scenario: MoGe-2 限制 CoreML 动态分区
- **WHEN** 系统以 CoreML 创建 MoGe-2 Session
- **THEN** CoreML Provider options 包含 `RequireStaticInputShapes=1`，且不包含 `ModelFormat=MLProgram`

#### Scenario: 其他模型不继承 MoGe-2 限制
- **WHEN** 系统以 CoreML 创建 BEN2、DA3 或 Upscale Session
- **THEN** CoreML Provider 不包含 MoGe-2 的静态输入限制

#### Scenario: 自动选择 CoreML
- **WHEN** 任务请求自动设备且 CoreML 与 CPU Provider 都可用
- **THEN** CoreML 的优先级高于 CPU，并保留 CPU fallback

#### Scenario: CoreML 不可用
- **WHEN** 任务请求 CoreML 但 ONNX Runtime 只提供 CPU Provider
- **THEN** 系统使用 CPU Provider

### Requirement: MoGe-2 可在 CoreML 模式推理
系统 MUST 支持 MoGe-2 ONNX 模型在兼容 Apple Silicon CoreML 环境中创建 Session 并完成推理，不得因 AnyImage 强制选择 MLProgram 而在创建模型时失败。

#### Scenario: Apple Silicon 执行 MoGe-2
- **WHEN** M2 或 M4 用户选择 CoreML 并运行 MoGe-2 功能
- **THEN** 系统成功创建 CoreML Session 并完成至少一帧 MoGe-2 推理

#### Scenario: 其他 AI 模型继续使用 CoreML
- **WHEN** 用户选择 CoreML 并运行 BEN2 或 Upscale
- **THEN** 对应模型继续完成 Session 创建和推理

