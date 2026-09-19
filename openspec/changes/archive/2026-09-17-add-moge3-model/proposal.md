## Why

MoGe-3 ViT-L 的完整三次细化已在项目外通过 CPU ONNX Runtime 与 DirectML 原型验证。正式接入应沿用 MoGe 2 的工程流程，以最小改动增加模型选项，并完成动态输入和分辨率等级验证。

## What Changes

- 将已跑通的双 ONNX 图原型扩展到现有输入尺寸处理、宽高比和分辨率等级，建立可复现导出与精度比较流程。
- 验证通过后新增 `MOGE3_VITL` 模型选项、ONNX 资产下载和就绪检查，保留已有模型及默认值。
- 深度平面、裁切与全景统一按模型分派，推理统一采用现有 ONNX Runtime，复用几何产物。
- 两个 ONNX 图、体素邻域生成与三次细化封装在 MoGe 3 模型内部；复用现有 Operator、节点资产、Job 参数和用户操作流程。
- 以完整细化、数值一致性、执行提供程序兼容性与可用性能作为正式接入门槛。

## Capabilities

### New Capabilities

- `moge3-model`: 完整 MoGe 3 的 ONNX 推理、模型选择、资产准备与几何工作流集成。

### Modified Capabilities

## Impact

改动集中在离线转换工具、模型登记、MoGe 3 ONNX 模块和必要的推理分派；模型枚举、下载与会话管理沿用既有机制。PyTorch、MoGe、FlexGEMM 与 Triton 仅用于隔离的离线转换及参考验证环境；正式 Server 沿用 ONNX Runtime 与现有后处理依赖。正式接入以动态尺寸、分辨率等级及完整流程验收通过为前提。
