# model-inference-memory Specification

## Purpose
TBD - created by archiving change release-model-inference-memory. Update Purpose after archive.
## Requirements

### Requirement: Cached model sessions survive inference cleanup

系统 SHALL 在清理一次推理使用的临时内存后保留对应模型的已加载 Session，使相同模型、Device 与 Runtime 的下一次请求复用该 Session。

#### Scenario: Matching request reuses the loaded model

- **WHEN** 一个模型操作成功完成临时推理内存清理，随后以相同模型、Device 与 Runtime 再次请求该模型
- **THEN** 系统复用同一个已加载 Session，且不重新从模型文件创建 Session

#### Scenario: All model families share the lifecycle

- **WHEN** BEN2、DA3、MoGe-2 或任一 Upscale 模型在支持清理的 Provider 上完成推理
- **THEN** 每个模型均遵循相同的 Session 保留与临时内存释放语义

### Requirement: Temporary GPU inference memory is released at operation completion

系统 SHALL 在 Execution Provider 支持 memory arena shrinkage 时，于一次成功业务推理的最后一次模型运行请求释放不再使用的临时 GPU arena，同时保留 Session 持有的模型资源。

#### Scenario: Single-run inference releases temporary memory

- **WHEN** 一次业务推理只执行一次模型运行并成功返回
- **THEN** 该次模型运行请求在结束时收缩支持回收的 GPU memory arena

#### Scenario: Multi-frame inference releases after the final frame

- **WHEN** 一次业务推理依次处理多个输入帧
- **THEN** 中间帧不触发 arena shrinkage，最后一帧的模型运行请求触发 arena shrinkage

#### Scenario: Tiled inference releases after the final tile

- **WHEN** Upscale 为一个或多个输入帧执行多次分块模型运行
- **THEN** 中间分块与中间帧不触发 arena shrinkage，整个业务推理的最后一个分块触发 arena shrinkage

### Requirement: Unsupported providers retain existing inference behavior

系统 MUST 只向明确支持所选 memory arena shrinkage 配置的 Execution Provider 提交该配置；其他 Provider SHALL 按原有运行方式执行。

#### Scenario: Provider does not support GPU arena shrinkage

- **WHEN** 模型 Session 使用 CPU、DirectML、CoreML 或其他未声明支持该 GPU arena shrinkage 配置的 Provider
- **THEN** 系统不提交对应的 Provider 或 Run 清理配置，且推理继续正常执行

### Requirement: Inference results and failure contracts remain stable

临时内存释放 SHALL 不改变模型输入、模型输出、Job 产物或取消检查；所有 ONNX 模型的 Session 创建与推理资源错误 SHALL 由共享 Runtime 边界提供一致、可读的错误。

#### Scenario: Cleanup-enabled inference returns the same model result

- **WHEN** 对相同输入与模型分别执行启用和未启用临时内存释放的推理
- **THEN** 两次推理返回相同结构、尺寸、dtype 与数值语义的模型结果

#### Scenario: ONNX provider resource failure

- **WHEN** 任一 ONNX 模型的 Execution Provider 因 GPU 或系统内存不足而无法创建 Session 或完成推理
- **THEN** 系统返回共享的可读资源错误，且既有 Session 缓存与临时内存释放语义保持不变

### Requirement: Resource failures recover model cache safely

系统 SHALL 只在共享 ONNX Runtime 明确标记资源失败时清空三个模型 Session 槽位，并 SHALL 根据失败阶段采用有限且可预测的恢复行为。

#### Scenario: First session load exhausts resources
- **WHEN** 任一模型 Session 首次创建因 ONNX Provider 资源不足而失败
- **THEN** 系统清空 background、geometry 和 upscale Session，并重新创建当前 Session 一次

#### Scenario: Retried session load succeeds
- **WHEN** 清空缓存后的唯一一次 Session 创建重试成功
- **THEN** 当前操作继续执行，只有当前模型重新进入对应缓存槽位

#### Scenario: Retried session load still exhausts resources
- **WHEN** 清空缓存后的 Session 创建重试仍因资源不足而失败
- **THEN** 系统停止重试、保持全部槽位为空并返回资源错误

#### Scenario: Inference exhausts resources
- **WHEN** 已加载模型在推理期间因 ONNX Provider 资源不足而失败
- **THEN** 系统清空全部模型 Session、返回原资源错误且不自动重试推理

#### Scenario: Inference fails for another reason
- **WHEN** 模型操作因普通 Runtime 错误、无效输入或任务取消而失败
- **THEN** 系统保留现有缓存 Session，不执行 OOM 恢复

#### Scenario: Inference succeeds
- **WHEN** 模型加载与推理成功完成
- **THEN** background、geometry 和 upscale 继续按现有三个槽位复用 Session
