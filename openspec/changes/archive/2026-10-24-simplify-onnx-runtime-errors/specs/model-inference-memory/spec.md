## MODIFIED Requirements

### Requirement: Inference results and failure contracts remain stable

临时内存释放 SHALL 不改变模型输入、模型输出、Job 产物或取消检查；所有 ONNX 模型的 Session 创建与推理资源错误 SHALL 由共享 Runtime 边界提供一致、可读的错误。

#### Scenario: Cleanup-enabled inference returns the same model result

- **WHEN** 对相同输入与模型分别执行启用和未启用临时内存释放的推理
- **THEN** 两次推理返回相同结构、尺寸、dtype 与数值语义的模型结果

#### Scenario: ONNX provider resource failure

- **WHEN** 任一 ONNX 模型的 Execution Provider 因 GPU 或系统内存不足而无法创建 Session 或完成推理
- **THEN** 系统返回共享的可读资源错误，且既有 Session 缓存与临时内存释放语义保持不变
