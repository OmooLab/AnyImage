## ADDED Requirements

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
