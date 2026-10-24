## ADDED Requirements

### Requirement: Shared ONNX calls present consistent failures

系统 SHALL 在共享 ONNX Runtime 边界转换 Session 创建和模型运行期间的底层异常，使所有 ONNX 模型获得一致且可读的错误，同时保留原始异常链用于诊断。

#### Scenario: Session creation runs out of memory
- **WHEN** ONNX Runtime 创建 Session 时明确报告 GPU 或系统内存不足
- **THEN** 系统返回说明模型加载因 GPU 或系统内存不足而失败的普通运行错误

#### Scenario: Model execution runs out of memory
- **WHEN** 任一 ONNX 模型运行时明确报告 GPU 或系统内存不足
- **THEN** 系统返回说明模型执行因 GPU 或系统内存不足而失败的普通运行错误

#### Scenario: Provider error cannot be decoded
- **WHEN** Session 创建或模型运行期间因底层 Provider 错误产生 Unicode 解码失败
- **THEN** 系统说明 ONNX Runtime 无法报告 Provider 错误并提示 GPU 或系统内存不足是可能原因，不直接显示 codec 异常

#### Scenario: Non-resource runtime failure
- **WHEN** Session 创建或模型运行产生不属于资源不足的 ONNX Runtime 异常
- **THEN** 系统保留原始原因并明确错误发生在模型加载或模型执行阶段

### Requirement: Explicit devices match their execution providers

系统 MUST 仅在 `auto` 设备模式下自动选择替代 Provider；显式设备请求 SHALL 使用对应 Provider，或者在该 Provider 不可用时明确失败。

#### Scenario: Automatic provider selection
- **WHEN** 调用方请求 `auto` 且存在一个或多个可用 Provider
- **THEN** 系统按既有优先级选择加速 Provider并保留可用的后备 Provider

#### Scenario: Explicit provider is available
- **WHEN** 调用方显式请求 CUDA、DirectML、CoreML 或 CPU 且对应 Provider 可用
- **THEN** 系统使用对应 Provider 创建 Session

#### Scenario: Explicit provider is unavailable
- **WHEN** 调用方显式请求的 Provider 不可用
- **THEN** 系统明确报告该 Provider 不可用，不静默切换到另一设备

#### Scenario: CoreML session uses CPU fallback
- **WHEN** 调用方选择 CoreML 且 CoreML 与 CPU Provider 均可用
- **THEN** 系统保持 CoreML 优先并将 CPU 配置为该 Session 的后备 Provider
